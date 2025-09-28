# PlanExe REST API & Node.js Integration

This is a REST API wrapper and Node.js frontend for PlanExe, allowing you to build custom user interfaces using modern web technologies while leveraging the powerful AI planning capabilities of PlanExe.

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/neoneye/PlanExe.git
cd PlanExe

# Create environment file
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY

# Start the full stack
docker compose -f docker/docker compose.yml up

# Access the application
# API: http://localhost:8080
# UI: http://localhost:3000
```

### Option 2: Manual Setup

#### Start the Python API Server

```bash
# Install API dependencies
pip install fastapi uvicorn sse-starlette

# Start the API server
python -m planexe_api.api

# API will be available at http://localhost:8080
```

#### Start the Node.js Frontend

```bash
# Install Node.js dependencies
cd nodejs-client && npm install && cd ..
cd nodejs-ui && npm install

# Build the React app
npm run build

# Start the UI server
npm run server

# UI will be available at http://localhost:3000
```

## 📁 Project Structure

```
PlanExe/
├── planexe_api/              # FastAPI REST API
│   ├── api.py               # Main API server
│   ├── models.py            # Pydantic schemas
│   └── requirements.txt     # API dependencies
├── nodejs-client/           # Node.js client SDK
│   ├── index.js            # Client library
│   ├── index.d.ts          # TypeScript definitions
│   └── test.js             # Test script
├── nodejs-ui/              # React frontend
│   ├── src/                # React components
│   ├── server.js           # Express server
│   └── package.json        # UI dependencies
├── docker/                 # Docker configuration
│   ├── Dockerfile.api      # API container
│   ├── Dockerfile.ui       # UI container
│   └── docker compose.yml  # Full stack setup
└── docs/                   # Documentation
    └── API.md              # API documentation
```

## 🔧 API Endpoints

### Core Endpoints

- `GET /health` - Health check
- `GET /api/models` - Available LLM models
- `GET /api/prompts` - Example prompts
- `POST /api/plans` - Create new plan
- `GET /api/plans/{id}` - Get plan status
- `GET /api/plans/{id}/stream` - Real-time progress (SSE)
- `GET /api/plans/{id}/report` - Download HTML report

### Example Usage

```javascript
// Create a plan
const response = await fetch('http://localhost:8080/api/plans', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    prompt: 'Design a sustainable urban garden project',
    speed_vs_detail: 'ALL_DETAILS_BUT_SLOW'
  })
});

const plan = await response.json();
console.log('Plan ID:', plan.plan_id);
```

## 📚 Node.js Client SDK

### Installation

```bash
npm install planexe-client
```

### Usage

```javascript
const { PlanExeClient } = require('planexe-client');

const client = new PlanExeClient({
  baseURL: 'http://localhost:8080'
});

// Create a plan and watch progress
const plan = await client.createPlan({
  prompt: 'Design a mobile app for food delivery'
});

const watcher = client.watchPlan(plan.plan_id, {
  onProgress: (data) => {
    console.log(`Progress: ${data.progress_percentage}%`);
    console.log(`Status: ${data.progress_message}`);
  },
  onComplete: (data) => {
    console.log('Plan completed successfully!');
    // Download the report
    client.downloadReport(plan.plan_id);
  },
  onError: (error) => {
    console.error('Plan failed:', error.message);
  }
});

// The watcher automatically handles Server-Sent Events
// Call watcher.close() to stop watching
```

### TypeScript Support

```typescript
import { PlanExeClient, CreatePlanOptions } from 'planexe-client';

const client = new PlanExeClient({ baseURL: 'http://localhost:8080' });

const options: CreatePlanOptions = {
  prompt: 'Design a smart home system',
  speedVsDetail: 'BALANCED_SPEED_AND_DETAIL'
};

const plan = await client.createPlan(options);
```

## 🎨 React Frontend Features

The included React frontend provides:

- **Plan Creation Form** - Rich text input with example prompts
- **Model Selection** - Choose from available LLM models
- **Real-time Progress** - Live updates during plan generation
- **Plan Management** - View, cancel, and download plans
- **File Browser** - Access all generated plan files
- **Responsive Design** - Works on desktop and mobile

### Key Components

- `PlanCreate` - Form for creating new plans
- `PlanList` - View all plans with status
- `PlanDetail` - Real-time progress and results
- `usePlanExe` - React hook for API integration

## 🐳 Docker Deployment

### Development

```bash
docker compose -f docker/docker compose.yml up --build
```

### Production

```bash
# Set environment variables
export OPENROUTER_API_KEY=your-key-here

# Deploy with production settings
docker compose -f docker/docker compose.yml up -d
```

### Environment Variables

```env
# Required for paid models
OPENROUTER_API_KEY=your-openrouter-api-key

# Optional: Custom output directory
PLANEXE_RUN_DIR=/custom/path/to/plans

# Optional: Custom Python path
PATH_TO_PYTHON=/custom/python

# UI Configuration
PLANEXE_API_URL=http://localhost:8080
```

## 🔐 Configuration

### LLM Models

The API automatically detects available models from `llm_config.json`:

- **OpenRouter Models** - Require API key, high quality
- **Ollama Models** - Local, free, requires Ollama installation
- **LM Studio Models** - Local, free, requires LM Studio

### Speed vs Detail

Choose planning depth:

- `FAST_BUT_BASIC` - Quick overview, basic structure
- `BALANCED_SPEED_AND_DETAIL` - Good balance (recommended)
- `ALL_DETAILS_BUT_SLOW` - Comprehensive analysis

## 🛠️ Development

### API Development

```bash
# Install dependencies
pip install -e '.[gradio-ui,flask-ui]'
pip install -r planexe_api/requirements.txt

# Start with auto-reload
uvicorn planexe_api.api:app --reload --host 0.0.0.0 --port 8080
```

### Frontend Development

```bash
cd nodejs-ui

# Start development server with hot reload
npm run dev

# Build for production
npm run build
```

### Testing

```bash
# Test the Node.js client
cd nodejs-client
npm test

# Test API endpoints
curl http://localhost:8080/health
```

## 📖 Documentation

- [API Documentation](docs/API.md) - Complete REST API reference
- [Client SDK Documentation](nodejs-client/README.md) - Node.js client guide
- [Original PlanExe README](README.md) - Core PlanExe documentation

## 🤝 Integration Examples

### Express.js Integration

```javascript
const express = require('express');
const { PlanExeClient } = require('planexe-client');

const app = express();
const planexe = new PlanExeClient();

app.post('/create-plan', async (req, res) => {
  try {
    const plan = await planexe.createPlan({
      prompt: req.body.prompt
    });
    res.json({ planId: plan.plan_id });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});
```

### Next.js Integration

```javascript
// pages/api/plans.js
import { PlanExeClient } from 'planexe-client';

const client = new PlanExeClient({
  baseURL: process.env.PLANEXE_API_URL
});

export default async function handler(req, res) {
  if (req.method === 'POST') {
    const plan = await client.createPlan(req.body);
    res.json(plan);
  }
}
```

## 🐛 Troubleshooting

### Common Issues

1. **CORS Errors** - Use the provided proxy configuration
2. **API Connection Failed** - Ensure API server is running on port 8080
3. **Plan Creation Fails** - Check LLM model availability and API keys
4. **SSE Stream Disconnects** - Network timeouts, implement reconnection logic

### Debug Mode

```bash
# Enable debug logging for API
DEBUG=1 python -m planexe_api.api

# Enable verbose client logging
const client = new PlanExeClient({ debug: true });
```

## 🚦 Limitations

- Server-Sent Events may not work through some proxies
- Large plan outputs may take significant time to generate
- Some LLM models require paid API keys
- Docker setup requires sufficient disk space for plan outputs

## 🔄 Migration from Original UI

If you're migrating from the original Gradio or Flask UI:

1. **Data Compatibility** - Plan outputs use the same format
2. **API Keys** - Same environment variables work
3. **Configuration** - `llm_config.json` is used as-is
4. **Parallel Usage** - Can run alongside existing UIs

## 📞 Support

- **Issues** - [GitHub Issues](https://github.com/neoneye/PlanExe/issues)
- **API Docs** - [docs/API.md](docs/API.md)
- **Discord** - [PlanExe Discord](https://neoneye.github.io/PlanExe-web/discord.html)