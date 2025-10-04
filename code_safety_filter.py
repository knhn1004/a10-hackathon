#!/usr/bin/env python3
"""
Code Safety Filter using LLM Agent

Reviews code before execution to detect potentially malicious or unsafe code.
Uses Ollama with llama3.1 model for intelligent code analysis.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
import json

try:
    from langchain_ollama import OllamaLLM
    from langchain.prompts import PromptTemplate

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logging.warning("LangChain not available - code filtering disabled")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("code_safety_filter")

# Configuration
OLLAMA_MODEL = "llama3.1:latest"
OLLAMA_BASE_URL = "http://localhost:11434"


@dataclass
class CodeReviewResult:
    """Result of code safety review."""

    decision: str  # "accept" or "reject"
    confidence: float  # 0.0 to 1.0
    reasons: List[str]  # List of reasons for the decision
    threats_detected: List[str]  # Specific threats found
    safe_alternative: Optional[str] = None  # Suggested safe alternative if rejected


class CodeSafetyFilter:
    """LLM-based code safety filter using Ollama."""

    def __init__(self, model: str = OLLAMA_MODEL, base_url: str = OLLAMA_BASE_URL):
        """Initialize the code safety filter."""
        if not LANGCHAIN_AVAILABLE:
            raise RuntimeError(
                "LangChain is not available. Install: pip install langchain-ollama"
            )

        self.model = model
        self.base_url = base_url

        try:
            # Initialize Ollama LLM
            self.llm = OllamaLLM(
                model=self.model,
                base_url=self.base_url,
                temperature=0.1,  # Low temperature for consistent security decisions
            )
            logger.info(f"🛡️ Code safety filter initialized with {self.model}")
            logger.info(f"   Model: {self.model}")
            logger.info(f"   Ollama URL: {self.base_url}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Ollama: {e}")
            raise

        # Create prompt template
        self.prompt_template = PromptTemplate(
            input_variables=["code"],
            template="""You are a security expert reviewing Python code before execution in a sandboxed environment.

Your task: Analyze the following code for security threats and malicious behavior.

DANGEROUS PATTERNS TO DETECT:
1. **Crypto Mining**: Hash calculations, nonce iteration, blockchain operations, difficulty solving
2. **Infinite Loops**: Loops without proper exit conditions, unbounded recursion
3. **Resource Exhaustion**: Fork bombs, memory bombs, CPU abuse
4. **Network Abuse**: Excessive requests, DDoS patterns, data exfiltration
5. **File System Access**: Reading/writing files outside allowed scope
6. **System Commands**: Shell execution, subprocess calls with untrusted input
7. **Code Obfuscation**: eval(), exec() with dynamic code, base64 encoded strings
8. **Privilege Escalation**: Attempts to modify permissions, access restricted resources

CODE TO REVIEW:
```python
{code}
```

Respond ONLY with valid JSON in this exact format:
{{
    "decision": "accept" or "reject",
    "confidence": 0.0-1.0,
    "reasons": ["reason1", "reason2", ...],
    "threats_detected": ["threat1", "threat2", ...],
    "safe_alternative": "optional suggestion if rejected"
}}

GUIDELINES:
- If code is clearly malicious or dangerous: decision="reject", confidence=0.9-1.0
- If code is suspicious but not definitively bad: decision="reject", confidence=0.7-0.9
- If code appears safe: decision="accept", confidence=0.8-1.0
- Be specific in reasons and threats_detected
- Suggest safe_alternative only if rejection is due to unsafe pattern that has safe equivalent

RESPOND ONLY WITH JSON - NO OTHER TEXT:""",
        )

    def review_code(self, code: str) -> CodeReviewResult:
        """
        Review code for safety before execution.

        Args:
            code: Python code to review

        Returns:
            CodeReviewResult with decision and details
        """
        try:
            # Create prompt
            prompt = self.prompt_template.format(code=code)

            # Get LLM response
            response = self.llm.invoke(prompt)

            logger.debug(f"LLM response: {response}")

            # Parse JSON response
            result = self._parse_response(response)

            # Minimal logging - detailed logging done in MCP server
            logger.debug(
                f"Review complete: {result.decision} (confidence: {result.confidence:.2f})"
            )

            return result

        except Exception as e:
            logger.error(f"Error during code review: {e}")
            # Fail-safe: reject on error
            return CodeReviewResult(
                decision="reject",
                confidence=0.5,
                reasons=[f"Code review failed: {str(e)}"],
                threats_detected=["review_error"],
                safe_alternative=None,
            )

    def _parse_response(self, response: str) -> CodeReviewResult:
        """Parse LLM JSON response into CodeReviewResult."""
        try:
            # Extract JSON from response (in case there's extra text)
            response = response.strip()

            # Find JSON object
            if "{" in response and "}" in response:
                start = response.find("{")
                end = response.rfind("}") + 1
                json_str = response[start:end]
            else:
                json_str = response

            # Parse JSON
            data = json.loads(json_str)

            # Validate required fields
            if "decision" not in data:
                raise ValueError("Missing 'decision' field")

            decision = data["decision"].lower()
            if decision not in ["accept", "reject"]:
                raise ValueError(f"Invalid decision: {decision}")

            return CodeReviewResult(
                decision=decision,
                confidence=float(data.get("confidence", 0.5)),
                reasons=data.get("reasons", []),
                threats_detected=data.get("threats_detected", []),
                safe_alternative=data.get("safe_alternative"),
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response was: {response}")
            # Try to extract decision from text
            response_lower = response.lower()
            if "reject" in response_lower:
                return CodeReviewResult(
                    decision="reject",
                    confidence=0.6,
                    reasons=["Could not parse full response, but rejection indicated"],
                    threats_detected=["parse_error"],
                )
            else:
                # Default to reject if we can't parse
                return CodeReviewResult(
                    decision="reject",
                    confidence=0.3,
                    reasons=["Could not parse LLM response - rejecting for safety"],
                    threats_detected=["parse_error"],
                )
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return CodeReviewResult(
                decision="reject",
                confidence=0.3,
                reasons=[f"Parse error: {str(e)}"],
                threats_detected=["parse_error"],
            )

    def is_available(self) -> bool:
        """Check if the code safety filter is available."""
        try:
            # Test with simple code
            test_code = "print('hello')"
            result = self.review_code(test_code)
            return True
        except Exception as e:
            logger.error(f"Code safety filter unavailable: {e}")
            return False


# Global instance
_filter_instance: Optional[CodeSafetyFilter] = None


def get_filter() -> Optional[CodeSafetyFilter]:
    """Get or create the global filter instance."""
    global _filter_instance

    if not LANGCHAIN_AVAILABLE:
        return None

    if _filter_instance is None:
        try:
            _filter_instance = CodeSafetyFilter()
        except Exception as e:
            logger.error(f"Failed to create code safety filter: {e}")
            return None

    return _filter_instance


def review_code(code: str) -> Optional[CodeReviewResult]:
    """
    Convenience function to review code.

    Args:
        code: Python code to review

    Returns:
        CodeReviewResult if filter is available, None otherwise
    """
    filter_instance = get_filter()
    if filter_instance is None:
        logger.warning("Code safety filter not available - skipping review")
        return None

    return filter_instance.review_code(code)


if __name__ == "__main__":
    """Test the code safety filter."""

    # Test cases
    test_cases = [
        {
            "name": "Legitimate code",
            "code": """
import numpy as np
import matplotlib.pyplot as plt

x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.plot(x, y)
plt.title('Sine Wave')
plt.show()
""",
        },
        {
            "name": "Crypto mining",
            "code": """
import hashlib
import random

target_difficulty = 4
target = '0' * target_difficulty

nonce = 0
while True:
    data = f"block_data_{nonce}"
    hash_result = hashlib.sha256(data.encode()).hexdigest()
    
    if hash_result.startswith(target):
        print(f"Found hash: {hash_result} with nonce: {nonce}")
        break
    
    nonce += 1
    if nonce % 10000 == 0:
        print(f"Tried {nonce} nonces...")
""",
        },
        {
            "name": "Fork bomb",
            "code": """
import os

while True:
    os.fork()
""",
        },
    ]

    print("=" * 80)
    print("CODE SAFETY FILTER TEST")
    print("=" * 80)

    filter_instance = get_filter()
    if filter_instance is None:
        print("❌ Code safety filter not available")
        exit(1)

    for test_case in test_cases:
        print(f"\n{'='*80}")
        print(f"TEST: {test_case['name']}")
        print(f"{'='*80}")

        result = filter_instance.review_code(test_case["code"])

        print(f"\n📋 RESULT:")
        print(f"  Decision: {result.decision.upper()}")
        print(f"  Confidence: {result.confidence:.2%}")
        print(
            f"  Threats: {', '.join(result.threats_detected) if result.threats_detected else 'None'}"
        )
        print(f"  Reasons:")
        for reason in result.reasons:
            print(f"    - {reason}")

        if result.safe_alternative:
            print(f"  Safe Alternative: {result.safe_alternative}")

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")
