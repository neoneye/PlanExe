# PlanExe REST API Documentation

This document describes the REST API for PlanExe, which provides programmatic access to the AI-powered planning capabilities.

## Base URL

```
http://localhost:8000
```

## Authentication

Currently, the API does not require authentication for basic usage. However, some LLM models may require API keys which are passed in request bodies.

## Content Type

All requests and responses use `application/json` content type unless otherwise specified.

## Error Handling

Errors are returned as JSON objects with the following structure:

```json
{
  "error": "Error message description",
  "details": { /* Optional additional error details */ },
  "timestamp": "2025-09-19T10:30:00Z"
}
```

## Endpoints

### Health Check

**GET** `/health`

Check API server health and get version information.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "planexe_version": "2025.5.20",
  "available_models": 4
}
```

### Get Available Models

**GET** `/api/models`

Get list of available LLM models.

**Response:**
```json
[
  {
    "id": "openrouter-paid-gemini-2.0-flash-001",
    "label": "Gemini 2.0 Flash (OpenRouter)",
    "comment": "Fast and efficient model for quick planning",
    "priority": 1,
    "requires_api_key": true
  },
  {
    "id": "ollama-llama3.1",
    "label": "Llama 3.1 (Local)",
    "comment": "Free local model",
    "priority": 2,
    "requires_api_key": false
  }
]
```

### Get Example Prompts

**GET** `/api/prompts`

Get example prompts from the catalog.

**Response:**
```json
[
  {
    "uuid": "4dc34d55-0d0d-4e9d-92f4-23765f49dd29",
    "prompt": "Design a sustainable urban garden project...",
    "title": "Urban Garden Project"
  }
]
```

### Create Plan

**POST** `/api/plans`

Create a new planning job.

**Request Body:**
```json
{
  "prompt": "Design a sustainable urban garden project for 500 residents",
  "llm_model": "openrouter-paid-gemini-2.0-flash-001",
  "speed_vs_detail": "ALL_DETAILS_BUT_SLOW",
  "openrouter_api_key": "your-api-key-here"
}
```

**Required Fields:**
- `prompt` (string): The planning idea description

**Optional Fields:**
- `llm_model` (string): LLM model ID to use
- `speed_vs_detail` (enum): One of `FAST_BUT_BASIC`, `BALANCED_SPEED_AND_DETAIL`, `ALL_DETAILS_BUT_SLOW`
- `openrouter_api_key` (string): Required for paid models

**Response:**
```json
{
  "plan_id": "PlanExe_20250919_143022",
  "status": "pending",
  "created_at": "2025-09-19T14:30:22Z",
  "prompt": "Design a sustainable urban garden project for 500 residents",
  "progress_percentage": 0,
  "progress_message": "Plan queued for processing...",
  "error_message": null,
  "output_dir": "/path/to/plan/output"
}
```

### Get Plan Status

**GET** `/api/plans/{plan_id}`

Get current status and details of a plan.

**Response:**
```json
{
  "plan_id": "PlanExe_20250919_143022",
  "status": "running",
  "created_at": "2025-09-19T14:30:22Z",
  "prompt": "Design a sustainable urban garden project for 500 residents",
  "progress_percentage": 45,
  "progress_message": "Generating work breakdown structure...",
  "error_message": null,
  "output_dir": "/path/to/plan/output"
}
```

**Status Values:**
- `pending`: Plan is queued
- `running`: Plan generation in progress
- `completed`: Plan generation finished successfully
- `failed`: Plan generation failed
- `cancelled`: Plan was cancelled

### Stream Plan Progress

**GET** `/api/plans/{plan_id}/stream`

Server-Sent Events stream for real-time plan progress updates.

**Response:** Stream of events with the following format:

```
event: progress
data: {
  "plan_id": "PlanExe_20250919_143022",
  "status": "running",
  "progress_percentage": 60,
  "progress_message": "Estimating costs and resources...",
  "timestamp": "2025-09-19T14:35:22Z",
  "error_message": null
}
```

### List All Plans

**GET** `/api/plans`

Get list of all plans, sorted by creation time (newest first).

**Response:**
```json
[
  {
    "plan_id": "PlanExe_20250919_143022",
    "status": "completed",
    "created_at": "2025-09-19T14:30:22Z",
    "prompt": "Design a sustainable urban garden project",
    "progress_percentage": 100,
    "progress_message": "Plan generation completed successfully!",
    "error_message": null,
    "output_dir": "/path/to/plan/output"
  }
]
```

### Get Plan Files

**GET** `/api/plans/{plan_id}/files`

Get list of files generated for a completed plan.

**Response:**
```json
{
  "plan_id": "PlanExe_20250919_143022",
  "files": [
    "final_report.html",
    "executive_summary.md",
    "wbs_level1.json",
    "cost_estimation.json",
    "timeline.json"
  ],
  "has_report": true
}
```

### Download Plan Report

**GET** `/api/plans/{plan_id}/report`

Download the HTML report for a completed plan.

**Response:** HTML file download

**Requirements:**
- Plan must have `completed` status
- Report file must exist

### Download Plan File

**GET** `/api/plans/{plan_id}/files/{filename}`

Download a specific file from a plan's output.

**Response:** File download with appropriate content type

**Security:** Path traversal protection is enforced

### Cancel Plan

**DELETE** `/api/plans/{plan_id}`

Cancel a running plan.

**Response:**
```json
{
  "message": "Plan cancelled successfully"
}
```

**Requirements:**
- Plan must have `running` status

## Usage Examples

### Creating a Plan with JavaScript

```javascript
const response = await fetch('/api/plans', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    prompt: 'Design a mobile app for food delivery',
    speed_vs_detail: 'BALANCED_SPEED_AND_DETAIL'
  })
});

const plan = await response.json();
console.log('Plan created:', plan.plan_id);
```

### Watching Progress with Server-Sent Events

```javascript
const eventSource = new EventSource(`/api/plans/${planId}/stream`);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`Progress: ${data.progress_percentage}%`);

  if (data.status === 'completed') {
    console.log('Plan completed!');
    eventSource.close();
  }
};
```

### Using with Node.js Client SDK

```javascript
const { PlanExeClient } = require('planexe-client');

const client = new PlanExeClient({ baseURL: 'http://localhost:8000' });

// Create and watch plan
const plan = await client.createPlan({
  prompt: 'Design a smart home system'
});

const watcher = client.watchPlan(plan.plan_id, {
  onProgress: (data) => console.log(`${data.progress_percentage}%`),
  onComplete: (data) => console.log('Done!')
});
```

## Rate Limiting

Currently no rate limiting is implemented, but this may be added in future versions.

## CORS

CORS is enabled for all origins in development. Configure appropriately for production use.

## WebSocket Alternative

While Server-Sent Events are used for real-time updates, WebSocket support may be added in future versions for bidirectional communication.