# Dashboard Visual Guide

## Dashboard Overview

The Code Sandbox Observability Dashboard provides a comprehensive, real-time view of all running containers.

## Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  🐳 Code Sandbox Observability                                              │
│  🟢 Real-time monitoring • Updated every 2 seconds                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │Total Containers │  │   Total CPU     │  │  Total Memory   │  ...        │
│  │       5         │  │     45.3%       │  │    1250 MB      │             │
│  │  3 running      │  │                 │  │                 │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────┐  ┌────────────────────────────────┐    │
│  │  CPU Usage Over Time           │  │  Memory Usage Over Time        │    │
│  │                                │  │                                │    │
│  │      📈 Line Chart             │  │      📈 Line Chart             │    │
│  │   (60 seconds history)         │  │   (60 seconds history)         │    │
│  │                                │  │                                │    │
│  └────────────────────────────────┘  └────────────────────────────────┘    │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Active Containers                                                           │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────┐               │
│  │  sandbox_a1b2c3d4                           [🟢 running] │               │
│  │                                                          │               │
│  │  CPU: 12.5%        ████████░░░░░░░░                     │               │
│  │  Memory: 45 MB / 512 MB    ████░░░░░░░░░░░ (8.8%)      │               │
│  │  CPU Avg (1m): 10.2%                                    │               │
│  │  Uptime: 2m 15s                                         │               │
│  └─────────────────────────────────────────────────────────┘               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────┐               │
│  │  sandbox_e5f6g7h8                           [🟢 running] │               │
│  │                                                          │               │
│  │  CPU: 5.3%         ██░░░░░░░░░░░░░░                     │               │
│  │  Memory: 128 MB / 512 MB   ██████░░░░░░░░░ (25.0%)     │               │
│  │  CPU Avg (1m): 6.1%                                     │               │
│  │  Uptime: 1m 8s                                          │               │
│  └─────────────────────────────────────────────────────────┘               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Color Scheme

The dashboard uses a dark mode theme optimized for long monitoring sessions:

- **Background**: Deep navy blue (#0f172a)
- **Cards**: Slate gray (#1e293b)
- **Text**: Light gray (#f1f5f9)
- **Accent**: Blue (#3b82f6)
- **Success**: Green (#10b981) - for running containers
- **Danger**: Red (#ef4444) - for stopped containers
- **Warning**: Orange (#f59e0b)

## Interactive Elements

### Container Cards

- **Hover**: Cards lift slightly and border highlights
- **Click**: Opens detailed inspection modal
- **Progress Bars**: Animated fills for CPU and memory

### Charts

- **Auto-scaling**: Y-axis adjusts to data range
- **Smooth updates**: Transitions without jarring jumps
- **Tooltips**: Hover to see exact values

### Status Badges

```
┌─────────────┐
│  🟢 running │  Green background
└─────────────┘

┌─────────────┐
│  🔴 stopped │  Red background
└─────────────┘
```

## Detail Modal

Click any container card to see detailed information:

```
┌───────────────────────────────────────────────────────────────┐
│  Container: sandbox_a1b2c3d4                              [×] │
├───────────────────────────────────────────────────────────────┤
│                                                                │
│  Basic Information                                             │
│  ────────────────                                             │
│  ID: a1b2c3d4                                                 │
│  Image: code-sandbox:latest                                   │
│  Status: running                                              │
│  Created: 2024-10-03 14:30:22                                │
│  PID: 12345                                                   │
│                                                                │
│  Resource Limits                                              │
│  ────────────────                                             │
│  Memory Limit: 512 MB                                         │
│  CPU Quota: 50000                                             │
│  CPU Period: 100000                                           │
│                                                                │
│  Performance Statistics (Last 5 min)                          │
│  ────────────────────────────────────                        │
│  CPU: Min: 2.1% | Max: 18.5% | Avg: 8.3%                    │
│  Memory: Min: 32 MB | Max: 67 MB | Avg: 45 MB                │
│  Sample Count: 300                                            │
│                                                                │
│  Network                                                       │
│  ────────                                                     │
│  IP Address: 172.17.0.3                                       │
│  Networks: bridge                                             │
│  Ports: {"8000/tcp": "34567"}                                │
│                                                                │
│  Full Inspect Data                                            │
│  ────────────────                                             │
│  {                                                            │
│    "Id": "a1b2c3d4...",                                       │
│    "Created": "2024-10-03T14:30:22Z",                        │
│    "State": {                                                 │
│      "Status": "running",                                     │
│      "Pid": 12345,                                           │
│      ...                                                      │
│    },                                                         │
│    ...                                                        │
│  }                                                            │
│                                                                │
└───────────────────────────────────────────────────────────────┘
```

## Responsive Design

The dashboard adapts to different screen sizes:

### Desktop (> 1200px)

- 4 stat cards in a row
- 2 charts side-by-side
- Container cards in grid

### Tablet (768px - 1200px)

- 2 stat cards per row
- Charts stacked
- Container cards single column

### Mobile (< 768px)

- 1 stat card per row
- Charts full width
- Optimized touch targets

## Real-time Updates

### Update Cycle (every 2 seconds)

1. Fetch `/api/overview` → Update stat cards
2. Fetch `/api/system?limit=60` → Update charts
3. Process container data → Update container cards
4. Smooth animations for all changes

### Visual Indicators

- **Green pulse dot**: System actively updating
- **Chart animations**: Smooth line transitions
- **Progress bars**: Animated width changes
- **No flicker**: Uses Chart.js 'none' mode for smooth updates

## Usage Tips

### Monitoring Multiple Containers

- Sort by CPU usage (highest first)
- Watch for red status badges (stopped containers)
- Monitor aggregate metrics in header cards

### Performance Analysis

- Check CPU Avg (1m) for sustained load
- Compare current vs historical in charts
- Use stats summary for min/max ranges

### Debugging Issues

- Click container for full inspect data
- Check PID (0 = not running)
- Review resource limits vs usage
- Check exit code and error messages

## Keyboard Shortcuts

- **ESC**: Close detail modal
- **F5**: Manual refresh
- **Ctrl+Click**: Open inspect in new modal

## API Examples for Custom Integration

### Fetch Overview

```javascript
const response = await fetch("/api/overview");
const data = await response.json();
console.log(`Running: ${data.summary.running_containers}`);
```

### Get Container Metrics

```javascript
const response = await fetch("/api/containers/abc123?limit=60");
const data = await response.json();
const latest = data.metrics[data.metrics.length - 1];
console.log(`CPU: ${latest.cpu_percent}%`);
```

### Stream Updates

```javascript
setInterval(async () => {
  const response = await fetch("/api/system?limit=1");
  const data = await response.json();
  updateUI(data.metrics[0]);
}, 2000);
```

## Customization

### Change Update Interval

Edit `dashboard.html`:

```javascript
// Line ~800
setInterval(updateDashboard, 2000); // Change 2000 to your interval (ms)
```

### Change Chart Colors

Edit `dashboard.html`:

```javascript
// Line ~600
borderColor: '#3b82f6',  // Change to your color
backgroundColor: 'rgba(59, 130, 246, 0.1)',
```

### Change History Duration

Edit `monitor.py`:

```python
METRICS_HISTORY_SIZE = 300  # Change to desired sample count
# At 1 sample/second: 300 = 5 minutes
```

## Troubleshooting

### Dashboard shows "Loading..."

- Check Docker is running: `docker info`
- Check dashboard server: `curl http://localhost:8080/api/health`
- Check browser console for errors

### No containers shown

- Create sandboxes: They must have label `sandbox=1`
- Check with: `docker ps --filter "label=sandbox=1"`

### Charts not updating

- Check network tab in browser DevTools
- Verify API endpoints return data
- Check for JavaScript errors

### High CPU usage in browser

- Reduce update interval
- Limit chart history points
- Close detail modal when not needed

## Best Practices

1. **Keep dashboard open during development** to catch resource issues early
2. **Monitor aggregate CPU/memory** to avoid overloading system
3. **Check uptime** to identify containers that aren't auto-cleaning
4. **Use inspect modal** for debugging specific container issues
5. **Watch for memory leaks** in long-running sandboxes

## Screenshots

Since this is a code-only implementation, here are key visual moments:

### Initial Load

- Smooth fade-in of all elements
- Cards populate with data
- Charts draw from left to right

### Container Creation

- New card appears at bottom
- Stat cards update immediately
- Charts show spike in metrics

### Container Deletion

- Card fades out smoothly
- Stat cards update
- Charts show drop

### Error State

- Red error banner at top
- Helpful error message
- Retry guidance

## Accessibility

- Semantic HTML5 elements
- ARIA labels where needed
- Keyboard navigation support
- High contrast colors
- Clear visual hierarchy
- Readable fonts (system fonts)

## Browser Support

Tested and working on:

- ✅ Chrome/Edge 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Mobile Safari
- ✅ Chrome Mobile

Requires:

- ES6+ JavaScript
- Fetch API
- CSS Grid
- CSS Flexbox
