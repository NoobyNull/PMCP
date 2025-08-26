# PerfectMPC Advanced Services Guide

## Overview

PerfectMPC now includes three powerful advanced services that extend its capabilities:

1. **Context 7 Service** - Advanced 7-layer context management
2. **Playwright Service** - Web automation and browser testing
3. **Sequential Thinking Service** - Step-by-step reasoning and logical problem decomposition

## 🧠 Context 7 Service

### Features
- **7-Layer Context Hierarchy**: Immediate, Session, Project, Domain, Historical, Global, Meta
- **Intelligent Context Merging**: Combine contexts with AI-powered summarization
- **Context Switching**: Switch between different contexts while preserving important information
- **Pattern Analysis**: Analyze context usage patterns and provide insights

### API Endpoints

#### Add Context
```bash
POST /api/context7/add
{
  "session_id": "my-session",
  "content": "Important context information",
  "layer": 1,  # ContextLayer.IMMEDIATE
  "priority": 2,  # ContextPriority.HIGH
  "metadata": {"source": "user_input"}
}
```

#### Get Layered Context
```bash
GET /api/context7/layered/{session_id}?max_tokens=4000&include_layers=1,2,3
```

#### Merge Contexts
```bash
POST /api/context7/merge
{
  "session_id": "my-session",
  "context_ids": ["ctx1", "ctx2", "ctx3"],
  "target_layer": 3
}
```

#### Switch Context
```bash
POST /api/context7/switch
{
  "session_id": "my-session",
  "new_context_id": "target-context",
  "preserve_immediate": true
}
```

#### Analyze Patterns
```bash
GET /api/context7/patterns/{session_id}
```

### Context Layers
1. **IMMEDIATE** (1) - Current conversation/task context
2. **SESSION** (2) - Current session context  
3. **PROJECT** (3) - Project-level context
4. **DOMAIN** (4) - Domain knowledge context
5. **HISTORICAL** (5) - Historical patterns and learnings
6. **GLOBAL** (6) - Global knowledge and patterns
7. **META** (7) - Meta-cognitive and reasoning context

## 🌐 Playwright Service

### Features
- **Multi-Browser Support**: Chromium, Firefox, WebKit
- **Web Automation**: Navigate, click, type, scroll
- **Data Extraction**: Text, links, screenshots
- **JavaScript Execution**: Run custom scripts on pages
- **Session Management**: Multiple browser sessions per user

### API Endpoints

#### Create Browser Session
```bash
POST /api/playwright/session
{
  "session_id": "my-session",
  "browser_type": "chromium",
  "headless": true,
  "viewport": {"width": 1280, "height": 720}
}
```

#### Navigate to URL
```bash
POST /api/playwright/navigate
{
  "session_id": "my-session",
  "url": "https://example.com",
  "wait_until": "load"
}
```

#### Click Element
```bash
POST /api/playwright/click
{
  "session_id": "my-session",
  "selector": "button#submit",
  "timeout": 30000
}
```

#### Type Text
```bash
POST /api/playwright/type
{
  "session_id": "my-session",
  "selector": "input[name='username']",
  "text": "myusername",
  "delay": 100
}
```

#### Take Screenshot
```bash
POST /api/playwright/screenshot
{
  "session_id": "my-session",
  "full_page": false
}
```

#### Extract Text
```bash
POST /api/playwright/extract-text
{
  "session_id": "my-session",
  "selector": "body"
}
```

#### Extract Links
```bash
GET /api/playwright/links/{session_id}
```

#### Execute JavaScript
```bash
POST /api/playwright/javascript
{
  "session_id": "my-session",
  "script": "return document.title;"
}
```

#### Wait for Element
```bash
POST /api/playwright/wait-element
{
  "session_id": "my-session",
  "selector": ".loading-complete",
  "timeout": 30000
}
```

#### Get Session Info
```bash
GET /api/playwright/session/{session_id}
```

#### Close Session
```bash
DELETE /api/playwright/session/{session_id}
```

## 🤔 Sequential Thinking Service

### Features
- **Chain-of-Thought Processing**: Step-by-step reasoning
- **Multiple Reasoning Types**: Deductive, Inductive, Abductive, Analogical, Causal, Systematic
- **Thinking Steps**: Problem Analysis, Hypothesis Formation, Evidence Gathering, etc.
- **Solution Synthesis**: Combine thinking steps into coherent solutions
- **Branch Thinking**: Explore alternative reasoning paths
- **Chain Comparison**: Compare different thinking approaches

### API Endpoints

#### Start Thinking Chain
```bash
POST /api/thinking/chain
{
  "session_id": "my-session",
  "problem": "How to optimize database queries?",
  "reasoning_type": "systematic",
  "context": {"domain": "database_optimization"}
}
```

#### Add Thinking Step
```bash
POST /api/thinking/step
{
  "chain_id": "chain-uuid",
  "step_type": "evidence_gathering",
  "content": "Current query takes 2.5 seconds on average",
  "confidence": 0.8,
  "dependencies": ["previous-step-id"],
  "evidence": {"measurement": "query_time", "value": 2.5}
}
```

#### Validate Step
```bash
POST /api/thinking/validate
{
  "chain_id": "chain-uuid",
  "step_id": "step-uuid",
  "validation_result": true,
  "validation_notes": "Confirmed by performance testing"
}
```

#### Synthesize Solution
```bash
POST /api/thinking/synthesize/{chain_id}
```

#### Branch Thinking
```bash
POST /api/thinking/branch
{
  "chain_id": "chain-uuid",
  "step_id": "branch-point-step",
  "alternative_content": "Alternative approach: use caching",
  "reasoning_type": "systematic"
}
```

#### Compare Chains
```bash
POST /api/thinking/compare
{
  "chain_ids": ["chain1", "chain2", "chain3"]
}
```

#### Get Thinking Patterns
```bash
GET /api/thinking/patterns/{session_id}
```

### Thinking Step Types
- **PROBLEM_ANALYSIS** - Analyze and understand the problem
- **HYPOTHESIS_FORMATION** - Form hypotheses or potential solutions
- **EVIDENCE_GATHERING** - Collect relevant evidence and data
- **LOGICAL_REASONING** - Apply logical reasoning to evidence
- **SOLUTION_SYNTHESIS** - Combine insights into solutions
- **VALIDATION** - Validate solutions and reasoning
- **REFLECTION** - Reflect on the thinking process

### Reasoning Types
- **DEDUCTIVE** - General principles to specific conclusions
- **INDUCTIVE** - Specific observations to general principles  
- **ABDUCTIVE** - Best explanation for observations
- **ANALOGICAL** - Reasoning by similarity
- **CAUSAL** - Cause-and-effect reasoning
- **SYSTEMATIC** - Comprehensive step-by-step approach

## 🚀 Getting Started

### 1. Start the Server
```bash
cd /opt/PerfectMPC
source venv/bin/activate
python3 src/main.py
```

### 2. Check Service Status
```bash
curl http://192.168.0.78:8000/health
```

### 3. Test Context7 Service
```bash
# Add context
curl -X POST http://192.168.0.78:8000/api/context7/add \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session",
    "content": "Working on database optimization project",
    "layer": 3,
    "priority": 2
  }'

# Get layered context
curl http://192.168.0.78:8000/api/context7/layered/test-session
```

### 4. Test Sequential Thinking
```bash
# Start thinking chain
curl -X POST http://192.168.0.78:8000/api/thinking/chain \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session",
    "problem": "How to improve API response times?",
    "reasoning_type": "systematic"
  }'
```

### 5. Test Playwright (if installed)
```bash
# Create browser session
curl -X POST http://192.168.0.78:8000/api/playwright/session \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session",
    "browser_type": "chromium",
    "headless": true
  }'
```

## 📊 Admin Interface

The admin interface at http://192.168.0.78:8080 now shows the status of all services including:
- Context7 Service
- Playwright Service  
- Sequential Thinking Service

## 🔧 Configuration

The services use the existing configuration system and database connections. No additional configuration is required for basic functionality.

## 📝 Notes

- **Playwright Installation**: Run `pip install playwright` and `playwright install` for full browser support
- **Database Storage**: All services store data in MongoDB collections
- **Memory Usage**: Context7 maintains in-memory caches for performance
- **Session Management**: All services are session-aware and support multiple concurrent users

## 🎯 Use Cases

### Context7 Service
- Multi-layered conversation management
- Project context preservation
- Knowledge base organization
- Context-aware AI interactions

### Playwright Service  
- Web scraping and data extraction
- Automated testing of web applications
- Browser-based workflows
- Screenshot and monitoring services

### Sequential Thinking Service
- Complex problem solving
- Decision support systems
- Logical reasoning workflows
- AI-assisted analysis and planning

---

**🎉 Your PerfectMPC server now has advanced AI capabilities for context management, web automation, and sequential reasoning!**
