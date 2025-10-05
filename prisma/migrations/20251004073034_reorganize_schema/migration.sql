-- CreateTable
CREATE TABLE "users" (
    "id" TEXT NOT NULL,
    "githubId" TEXT NOT NULL,
    "username" TEXT NOT NULL,
    "email" TEXT,
    "name" TEXT,
    "avatarUrl" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "api_tokens" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "tokenHash" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "usageCount" INTEGER NOT NULL DEFAULT 0,
    "lastUsedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "revokedAt" TIMESTAMP(3),

    CONSTRAINT "api_tokens_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "mcp_requests" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "tool" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "sandboxId" TEXT,
    "codeLength" INTEGER,
    "url" TEXT,
    "resultPreview" TEXT,
    "errorMessage" TEXT,
    "executionTime" DOUBLE PRECISION,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "mcp_requests_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "containers" (
    "id" TEXT NOT NULL,
    "containerId" TEXT NOT NULL,
    "containerName" TEXT NOT NULL,
    "sandboxId" TEXT NOT NULL,
    "mcpRequestId" TEXT,
    "userId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deletedAt" TIMESTAMP(3),

    CONSTRAINT "containers_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "container_crashes" (
    "id" TEXT NOT NULL,
    "containerId" TEXT NOT NULL,
    "containerName" TEXT NOT NULL,
    "exitCode" INTEGER NOT NULL,
    "signal" TEXT,
    "oomKilled" BOOLEAN NOT NULL DEFAULT false,
    "stdout" TEXT,
    "stderr" TEXT,
    "crashedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "container_crashes_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "container_metrics" (
    "id" TEXT NOT NULL,
    "containerId" TEXT NOT NULL,
    "containerName" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "cpuPercent" DOUBLE PRECISION NOT NULL,
    "memoryUsageMb" DOUBLE PRECISION NOT NULL,
    "memoryLimitMb" DOUBLE PRECISION NOT NULL,
    "memoryPercent" DOUBLE PRECISION NOT NULL,
    "networkRxBytes" BIGINT NOT NULL,
    "networkTxBytes" BIGINT NOT NULL,
    "blockReadBytes" BIGINT NOT NULL,
    "blockWriteBytes" BIGINT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "container_metrics_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "llm_reviews" (
    "id" TEXT NOT NULL,
    "mcpRequestId" TEXT NOT NULL,
    "sandboxId" TEXT NOT NULL,
    "source" TEXT NOT NULL,
    "code" TEXT NOT NULL,
    "codeLength" INTEGER NOT NULL,
    "decision" TEXT NOT NULL,
    "confidence" DOUBLE PRECISION NOT NULL,
    "threatsDetected" TEXT[],
    "reasoning" TEXT,
    "reviewTime" DOUBLE PRECISION NOT NULL,
    "modelUsed" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "llm_reviews_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ml_predictions" (
    "id" TEXT NOT NULL,
    "containerId" TEXT NOT NULL,
    "containerName" TEXT NOT NULL,
    "prediction" TEXT NOT NULL,
    "confidence" DOUBLE PRECISION NOT NULL,
    "samples" INTEGER NOT NULL,
    "duration" DOUBLE PRECISION NOT NULL,
    "features" JSONB NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ml_predictions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "system_metrics" (
    "id" TEXT NOT NULL,
    "totalContainers" INTEGER NOT NULL,
    "runningContainers" INTEGER NOT NULL,
    "totalCpuPercent" DOUBLE PRECISION NOT NULL,
    "totalMemoryMb" DOUBLE PRECISION NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "system_metrics_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "users_githubId_key" ON "users"("githubId");

-- CreateIndex
CREATE UNIQUE INDEX "users_username_key" ON "users"("username");

-- CreateIndex
CREATE INDEX "users_githubId_idx" ON "users"("githubId");

-- CreateIndex
CREATE INDEX "users_username_idx" ON "users"("username");

-- CreateIndex
CREATE UNIQUE INDEX "api_tokens_tokenHash_key" ON "api_tokens"("tokenHash");

-- CreateIndex
CREATE INDEX "api_tokens_tokenHash_idx" ON "api_tokens"("tokenHash");

-- CreateIndex
CREATE INDEX "api_tokens_userId_idx" ON "api_tokens"("userId");

-- CreateIndex
CREATE INDEX "mcp_requests_userId_idx" ON "mcp_requests"("userId");

-- CreateIndex
CREATE INDEX "mcp_requests_sandboxId_idx" ON "mcp_requests"("sandboxId");

-- CreateIndex
CREATE INDEX "mcp_requests_createdAt_idx" ON "mcp_requests"("createdAt");

-- CreateIndex
CREATE INDEX "mcp_requests_status_idx" ON "mcp_requests"("status");

-- CreateIndex
CREATE INDEX "mcp_requests_tool_idx" ON "mcp_requests"("tool");

-- CreateIndex
CREATE UNIQUE INDEX "containers_containerId_key" ON "containers"("containerId");

-- CreateIndex
CREATE UNIQUE INDEX "containers_sandboxId_key" ON "containers"("sandboxId");

-- CreateIndex
CREATE INDEX "containers_containerId_idx" ON "containers"("containerId");

-- CreateIndex
CREATE INDEX "containers_sandboxId_idx" ON "containers"("sandboxId");

-- CreateIndex
CREATE INDEX "containers_userId_idx" ON "containers"("userId");

-- CreateIndex
CREATE INDEX "containers_mcpRequestId_idx" ON "containers"("mcpRequestId");

-- CreateIndex
CREATE INDEX "container_crashes_containerId_idx" ON "container_crashes"("containerId");

-- CreateIndex
CREATE INDEX "container_crashes_crashedAt_idx" ON "container_crashes"("crashedAt");

-- CreateIndex
CREATE INDEX "container_metrics_containerId_createdAt_idx" ON "container_metrics"("containerId", "createdAt");

-- CreateIndex
CREATE INDEX "container_metrics_createdAt_idx" ON "container_metrics"("createdAt");

-- CreateIndex
CREATE INDEX "llm_reviews_mcpRequestId_idx" ON "llm_reviews"("mcpRequestId");

-- CreateIndex
CREATE INDEX "llm_reviews_sandboxId_idx" ON "llm_reviews"("sandboxId");

-- CreateIndex
CREATE INDEX "llm_reviews_decision_idx" ON "llm_reviews"("decision");

-- CreateIndex
CREATE INDEX "llm_reviews_createdAt_idx" ON "llm_reviews"("createdAt");

-- CreateIndex
CREATE INDEX "ml_predictions_containerId_idx" ON "ml_predictions"("containerId");

-- CreateIndex
CREATE INDEX "ml_predictions_prediction_idx" ON "ml_predictions"("prediction");

-- CreateIndex
CREATE INDEX "ml_predictions_createdAt_idx" ON "ml_predictions"("createdAt");

-- CreateIndex
CREATE INDEX "system_metrics_createdAt_idx" ON "system_metrics"("createdAt");

-- AddForeignKey
ALTER TABLE "api_tokens" ADD CONSTRAINT "api_tokens_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "mcp_requests" ADD CONSTRAINT "mcp_requests_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "containers" ADD CONSTRAINT "containers_mcpRequestId_fkey" FOREIGN KEY ("mcpRequestId") REFERENCES "mcp_requests"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "container_crashes" ADD CONSTRAINT "container_crashes_containerId_fkey" FOREIGN KEY ("containerId") REFERENCES "containers"("containerId") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "container_metrics" ADD CONSTRAINT "container_metrics_containerId_fkey" FOREIGN KEY ("containerId") REFERENCES "containers"("containerId") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "llm_reviews" ADD CONSTRAINT "llm_reviews_mcpRequestId_fkey" FOREIGN KEY ("mcpRequestId") REFERENCES "mcp_requests"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ml_predictions" ADD CONSTRAINT "ml_predictions_containerId_fkey" FOREIGN KEY ("containerId") REFERENCES "containers"("containerId") ON DELETE CASCADE ON UPDATE CASCADE;
