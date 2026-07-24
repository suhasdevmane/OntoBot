---
title: Frontend User Interface
layout: post
category: docs
permalink: /docs/frontend_ui/
date: 2025-10-08
---


# Frontend UI Guide# Frontend User Interface


**Complete guide to OntoBot's React-based chat interface and visualization system.**The OntoBot frontend is a React-based web application that provides an intuitive interface for interacting with your smart building. It runs on **port 3000** and serves as the main entry point for users.


---## Overview


## Table of ContentsThe frontend consists of several key pages:

- **Home Dashboard**: Service overview and quick access

1. [Overview](#overview)- **Chat Interface**: Conversational interaction with the building

2. [Architecture](#architecture)- **Settings**: Model training and Rasa configuration

3. [Installation & Setup](#installation--setup)- **Health Monitoring**: Service status checks

4. [User Interface](#user-interface)- **Editor**: Rasa project file editor

5. [Chat Components](#chat-components)

6. [Visualization Display](#visualization-display)## Home Dashboard

7. [Building Switcher](#building-switcher)

8. [Configuration](#configuration)Access: `http://localhost:3000`

9. [Customization](#customization)

10. [Development](#development)### Features


---The home dashboard provides a visual overview of all available services with quick-launch buttons:


## Overview#### Data & Semantics

- **Jena Fuseki Server** (port 3030): Semantic Web Framework for SPARQL queries

### Technology Stack- **GraphDB** (port 7200): Graph database management system


**Framework**: React 18.2.0#### IoT Platform & Database Tools

- **ThingsBoard Server** (port 8082): IoT platform for device management

**Language**: JavaScript (ES6+)- **pgAdmin** (port 5050/5051): PostgreSQL administration interface

- **Adminer** (port 8282): Lightweight database management tool

**Styling**: CSS3 (custom styles)- **MySQL Server** (port 3307): Legacy telemetry database


**HTTP Client**: Axios 1.4.0#### Microservices & APIs

- **Microservices** (port 6001): Analytics and utility services

**Build Tool**: Webpack 5.88.0- **File Server** (port 8080): Shared artifacts server for models and results

- **3D API** (port 8091): API for 3D visualization services

**Development Server**: webpack-dev-server 4.15.1- **Visualiser** (port 8090): 3D building visualization


---#### Conversational Stack

- **Rasa Server** (port 5005): Conversational AI engine

### Key Features- **Rasa Editor** (port 6080): Project file editor and configuration

- **Duckling Server** (port 8000): Entity extraction for dates, times, and numbers

- 💬 **Real-time chat interface** with Rasa integration

- 📊 **Embedded chart visualization** (PNG/SVG artifacts)#### AI & ML Services

- 🏢 **Multi-building support** with dynamic switching- **NL2SPARQL Service** (port 6005): T5-based natural language to SPARQL translator

- 📥 **Data export** (CSV/JSON downloads)- **Ollama (Mistral)** (port 11434): Local LLM for summarization

- 📜 **Conversation history** with persistence- **Jupyter Lab** (port 8888): Interactive notebook environment

- 🔄 **Auto-refresh** for new messages

- 🎨 **Responsive design** (desktop/tablet/mobile)### Usage


---Click any service card to open it in a new browser tab. Services show their current status and purpose.


## Architecture## Chat Interface


### Component HierarchyAccess: `http://localhost:3000/chat` or click "Open Chatbot" from the home page


```### Features

App

├── ChatContainer#### Conversation Panel

│   ├── MessageList- **Message Input**: Type natural language questions about your building

│   │   ├── UserMessage- **Response Display**: View formatted responses with:

│   │   ├── BotMessage  - Text answers with UK-oriented units

│   │   │   ├── TextResponse  - Interactive charts and visualizations

│   │   │   ├── ChartDisplay  - Data tables

│   │   │   └── DataTable  - Downloadable artifacts

│   │   └── LoadingIndicator

│   ├── MessageInput#### Example Questions

│   │   ├── TextArea

```

│   │   └── SendButtonWhat is the CO2 level in zone 5.04?

│   └── ConversationHistoryShow me the temperature trend for room 2.11 today

│       └── HistoryItemAre there any anomalies in the HVAC system?

└── BuildingSwitcherWhat sensors are in the building?

    └── BuildingSelectorCompare humidity between zones 5.01 and 5.02

```


---#### Response Types


### Data Flow**1. Direct Answers**

- Latest sensor values

```- Sensor locations and metadata

User Input- Equipment status

    ↓

MessageInput (captures text)**2. Analytics Results**

    ↓- Time-series charts

POST /webhooks/rest/webhook- Statistical summaries (min, max, average)

    ↓- Trend analysis

Rasa Server- Anomaly detection

    ↓

Action Server (queries data, runs analytics)**3. Downloadable Artifacts**

    ↓- CSV data exports

Response Array- JSON analysis results

    ↓- Chart images

MessageList (displays responses)

    ↓### Chat Features

ChartDisplay (renders artifacts)

```- **Message History**: Scroll through previous conversations

- **Copy Response**: Copy answers to clipboard

---- **Export Chat**: Download conversation history

- **Clear Chat**: Reset conversation

### State Management

## Settings Page

**Local Component State** (React hooks):

- `messages`: Chat message historyAccess: `http://localhost:3000/settings`

- `currentInput`: User's current input text

- `isLoading`: Request in-flight indicatorThe Settings page is the command center for training and managing your Rasa models. It provides a 3-step workflow with real-time progress monitoring.

- `selectedBuilding`: Active building configuration

- `userId`: Unique user identifier (session-based)### Tabs


**No external state library** (Redux, MobX) - simple prop drilling suffices for this scale.#### 1. Model Training (Main Tab)


---**Step-by-Step Workflow:**


## Installation & Setup**Step 1: Train Model**

- Click **"Train"** button to start training job

### Prerequisites- Real-time logs stream in the console below

- Progress indicators show training status:

**Node.js**: v18.x or higher  - `idle`: Ready to train

  - `starting`: Initializing training

**npm**: v9.x or higher  - `preparing_data`: Loading training data

  - `training_core`: Training dialogue model

**Docker**: For backend services  - `training_nlu`: Training NLU model

  - `packaging`: Creating model archive

---  - `done`: Training complete ✓

  - `error`: Training failed

### Quick Start

**Step 2: Start Rasa Server**

**1. Navigate to frontend directory**:- After training, click **"Start Rasa"** to launch the Rasa server

```powershell- Monitor startup logs in real-time

cd rasa-frontend- Status indicators:

```  - `starting`: Server initializing

  - `healthy`: Server ready ✓

**2. Install dependencies**:

```powershell**Step 3: Verification**

npm install- Once both training and startup are complete, the green checkmark confirms the model is active

```- Chat interface is now ready to use


**3. Start development server**:**Log Management:**

```powershell- **Append Mode** (default): New logs are added to existing ones

npm start- **Replace Mode**: Each status check replaces the log window

```- Toggle with the "Append" checkbox

- Auto-scrolling keeps latest logs visible

**4. Open browser**:

```#### 2. Model Management

http://localhost:3000

```**Available Models List**

Shows all trained models with:

---- Model name (e.g., `20250108-123045-ancient-dust.tar.gz`)

- Creation timestamp

### Production Build- File size in MB

- Active status (✓ if currently loaded)

**Build optimized bundle**:

```powershell**Model Actions:**

npm run build- **Activate**: Load and restart Rasa with selected model

```  - Takes ~5 minutes (300 seconds)

  - Countdown timer shows estimated time remaining

**Output**: `build/` directory with minified assets  - Automatically restarts Rasa server


**Serve production build**:- **Delete**: Remove unused models

```powershell  - Confirmation required

npx serve -s build -l 3000  - Cannot delete currently active model

```  - Frees up disk space


---**Refresh Models**

Click "Refresh" to reload the models list from the server.

### Docker Deployment

#### 3. T5 Model Training Tab

**Dockerfile** (`rasa-frontend/Dockerfile`):

```dockerfile**⭐ NEW FEATURE**: GUI for training the T5 NL2SPARQL model

FROM node:18-alpine

Access: Settings → T5 Model Training

WORKDIR /app

See detailed documentation in [T5 Model Training Guide](./t5_training_guide.md)

COPY package*.json ./

RUN npm ci --only=production**Quick Overview:**

- Add training examples (question + SPARQL + sensors)

COPY . .- Train T5 model incrementally

RUN npm run build- Monitor training progress with real-time updates

- Deploy trained models to production

EXPOSE 3000- Test translations with the T5 playground


CMD ["npx", "serve", "-s", "build", "-l", "3000"]### Log Console

```

The compact log window at the bottom shows real-time output from:

**Build image**:- Training jobs (Rasa model training)

```powershell- Server startup

docker build -t ontobot-frontend:latest rasa-frontend/- Model activation

```- Error messages


**Run container**:**Features:**

```powershell- **Auto-scroll**: Automatically scrolls to latest entry

docker run -d -p 3000:3000 --name frontend ontobot-frontend:latest- **Copy All**: Copy entire log to clipboard

```- **Clear**: Reset log window

- **Append/Replace Toggle**: Choose log accumulation behavior

---

### Progress Indicators

## User Interface

Visual feedback throughout the workflow:

### Main Layout

**Training Badge:**

```- 🔵 `idle`: Ready to start

┌─────────────────────────────────────────────────────┐- 🟡 `starting`, `preparing_data`, `training_core`, `training_nlu`, `packaging`: In progress

│  OntoBot - Building 1 (ABACWS)         [Switch]     │- 🟢 `done`: Completed successfully

├─────────────────────────────────────────────────────┤- 🔴 `error`: Failed (check logs)

│                                                      │

│  Bot: Welcome! How can I help you today?            │**Start Badge:**

│                                                      │- 🔵 `idle`: Not started

│  User: show me temperature in zone 5.01             │- 🟡 `starting`: Server initializing

│                                                      │- 🟢 `healthy`: Running and ready

│  Bot: Here is the temperature data:                 │- 🔴 `error`: Failed to start

│  ┌──────────────────────────────────────────────┐  │

│  │  [Temperature Chart]                         │  │## Health Monitoring

│  │  Current: 21.5°C                             │  │

│  │  Mean: 21.6°C                                │  │Access: `http://localhost:3000/health`

│  └──────────────────────────────────────────────┘  │

│  [Download CSV] [Download JSON]                     │### Features

│                                                      │

├─────────────────────────────────────────────────────┤Monitor the health status of all OntoBot services:

│  Type your message...                    [Send]     │

└─────────────────────────────────────────────────────┘**Service Categories:**

```- Data & Semantics (Fuseki, GraphDB)

- IoT Platform (ThingsBoard, pgAdmin)

---- Microservices (Analytics, File Server, NL2SPARQL)

- Conversational Stack (Rasa, Duckling)

### Header Section- AI Services (Ollama, Jupyter)


**Elements**:**Status Indicators:**

- **Title**: "OntoBot - Building X"- ✅ **Healthy**: Service responding

- **Building Switcher**: Dropdown to select active building- ⚠️ **Warning**: Slow response

- **Status Indicator**: Connection status (connected/disconnected)- ❌ **Error**: Service unreachable

- ⏳ **Checking**: Status pending

**Component** (`src/components/Header.js`):

```javascript**Health Check Actions:**

function Header({ building, onBuildingChange, connectionStatus }) {- **Check All**: Test all services simultaneously

  return (- **Individual Check**: Test specific service

    <header className="app-header">- **Auto-refresh**: Toggle automatic status updates

      <h1>OntoBot - {building.name}</h1>- **Open Service**: Direct link to service URL

      <div className="header-controls">

        <BuildingSwitcher ### Health Endpoint Details

          currentBuilding={building} 

          onChange={onBuildingChange} Each service's health check uses its specific endpoint:

        />- `/health`: Standard health endpoint (most services)

        <StatusIndicator status={connectionStatus} />- `/$/ping`: Jena Fuseki

      </div>- `/version`: Rasa

    </header>- `/`: Homepage check (ThingsBoard, pgAdmin, etc.)

  );

}## Editor Interface

```

Access: `http://localhost:3000/editor` or via Rasa Editor service

---

### Features

### Chat Area

Integrated editor for modifying Rasa project files:

**Elements**:

- **Message List**: Scrollable container for messages**File Management:**

- **User Messages**: Right-aligned, blue background- Browse project structure

- **Bot Messages**: Left-aligned, gray background- Create new files

- **Charts**: Embedded PNG/SVG images- Delete existing files

- **Data Tables**: Tabular data display- Organize into folders

- **Download Buttons**: CSV/JSON export links

**Code Editor:**

---- Syntax highlighting for:

  - YAML (domain, config, rules, stories)

### Input Area  - Python (actions)

  - Markdown (documentation)

**Elements**:- Line numbers

- **Text Area**: Multi-line input for user queries- Auto-indentation

- **Send Button**: Submit query to Rasa- Search and replace

- **Loading Indicator**: Spinner during request

**Supported File Types:**

**Component** (`src/components/MessageInput.js`):- `domain.yml`: Intents, entities, responses, forms

```javascript- `config.yml`: Pipeline configuration

function MessageInput({ onSend, isLoading }) {- `nlu.yml`: Training examples

  const [input, setInput] = useState('');- `rules.yml`: Conversation rules

- `stories.yml`: Dialogue flows

  const handleSend = () => {- `actions.py`: Custom action code

    if (input.trim() && !isLoading) {

      onSend(input);**Safety Features:**

      setInput('');- Automatic backup before saving

    }- Syntax validation

  };- Confirmation for destructive actions


  const handleKeyPress = (e) => {## Responsive Design

    if (e.key === 'Enter' && !e.shiftKey) {

      e.preventDefault();The frontend is fully responsive and works on:

      handleSend();- Desktop browsers (recommended)

    }- Tablets

  };- Mobile devices (limited features)


  return (**Optimal Experience:**

    <div className="message-input">- Screen resolution: 1920x1080 or higher

      <textarea- Browser: Chrome, Firefox, Edge (latest versions)

        value={input}- JavaScript: Required

        onChange={(e) => setInput(e.target.value)}- Cookies: Required for authentication

        onKeyPress={handleKeyPress}

        placeholder="Type your message..."## Keyboard Shortcuts

        disabled={isLoading}

        rows={2}### Chat Interface

      />- `Enter`: Send message

      <button onClick={handleSend} disabled={isLoading || !input.trim()}>- `Shift+Enter`: New line in message

        {isLoading ? <Spinner /> : 'Send'}- `Ctrl+K`: Clear chat

      </button>- `Ctrl+C`: Copy last response

    </div>

  );### Settings Page

}- `Ctrl+T`: Start training

```- `Ctrl+R`: Refresh models

- `Ctrl+L`: Clear logs

---

### Editor

## Chat Components- `Ctrl+S`: Save file

- `Ctrl+F`: Find

### Message List- `Ctrl+H`: Find and replace

- `Ctrl+Z`: Undo

**Responsibilities**:- `Ctrl+Y`: Redo

- Display all messages in conversation

- Auto-scroll to newest message## Troubleshooting

- Render user and bot messages with distinct styling

### Common Issues

**Component** (`src/components/MessageList.js`):

```javascript**1. "Cannot connect to backend"**

import React, { useEffect, useRef } from 'react';- Verify all services are running: `docker ps`

import UserMessage from './UserMessage';- Check port 6001 (microservices) is accessible

import BotMessage from './BotMessage';- Clear browser cache and reload


function MessageList({ messages }) {**2. "Model training stuck"**

  const listRef = useRef(null);- Check logs for error messages

- Ensure sufficient disk space (>2GB)

  // Auto-scroll to bottom on new messages- Verify Rasa container has enough memory (>4GB)

  useEffect(() => {

    if (listRef.current) {**3. "Sensor dropdown empty"**

      listRef.current.scrollTop = listRef.current.scrollHeight;- Port 6001 must be accessible (not port 6000)

    }- Chrome blocks port 6000 as unsafe

  }, [messages]);- Restart microservices container


  return (**4. "Chat not responding"**

    <div className="message-list" ref={listRef}>- Verify Rasa server is healthy (Step 3 checkbox)

      {messages.map((msg, idx) => (- Check Rasa logs in Settings

        msg.sender === 'user' ? (- Ensure model is trained and activated

          <UserMessage key={idx} text={msg.text} />

        ) : (### Browser Console

          <BotMessage key={idx} message={msg} />

        )For debugging, open browser console:

      ))}- Chrome/Edge: `F12` or `Ctrl+Shift+I`

    </div>- Firefox: `F12` or `Ctrl+Shift+K`

  );

}Look for:

- Network errors (red in Network tab)

export default MessageList;- JavaScript errors (red in Console tab)

```- Failed API calls (check URL and response)


---## Advanced Configuration


### User Message### Environment Variables


**Component** (`src/components/UserMessage.js`):### Environment and CORS (.env)

{% raw %}
```javascript

function UserMessage({ text }) {When running with Docker Compose, the frontend and backend coordinate CORS and cookies using values from the repository's `.env` file.

  return (

    <div className="message user-message">1) Create your local `.env` from the template

      <div className="message-content">

        {text}

```powershell

      </div>Copy-Item -Path .env.example -Destination .env

      <div className="message-time"># Edit .env and replace placeholder values with your local credentials

        {new Date().toLocaleTimeString()}

```

      </div>

    </div>2) Set frontend-related variables in `.env`

  );

}- FRONTEND_ORIGIN=http://localhost:3000

- ALLOWED_ORIGINS=http://localhost:3000

export default UserMessage;- JWT_SECRET=change_me_in_prod

```

Notes

**CSS** (`src/styles/UserMessage.css`):- FRONTEND_ORIGIN and ALLOWED_ORIGINS are used by the File Server and Rasa Editor to allow cross-origin requests from the UI.

```css- Keep both values aligned with the actual UI URL (default http://localhost:3000). If you change the UI port, update both.

.user-message {- JWT_SECRET secures session cookies sent by the File Server. Use a strong value in non-dev environments.

  display: flex;

  flex-direction: column;3) Validate your compose configuration (optional but recommended)

  align-items: flex-end;

  margin: 10px 0;```powershell

}docker compose --env-file .env -f docker-compose.bldg1.yml config

# Or validate the stack you plan to run, e.g. bldg2/bldg3 with extras overlay

.user-message .message-content {# docker compose --env-file .env -f docker-compose.bldg2.yml config

  background-color: #007bff;# docker compose --env-file .env -f docker-compose.bldg3.yml -f docker-compose.extras.yml config

  color: white;```

  padding: 12px 16px;

  border-radius: 18px;If you see warnings like "The \"PG_THINGSBOARD_DB\" variable is not set.", add the missing variable to `.env` and re-run the command.

  max-width: 70%;

  word-wrap: break-word;4) Start the stack

}

```powershell

.user-message .message-time {docker compose --env-file .env -f docker-compose.bldg1.yml up -d --build

  font-size: 0.75rem;```

  color: #999;

  margin-top: 4px;### React app environment (advanced)

}

```Configure frontend behavior via environment variables:


---```bash

# React app environment

### Bot MessageREACT_APP_RASA_URL=http://localhost:5005

REACT_APP_FILE_SERVER_URL=http://localhost:8080

**Component** (`src/components/BotMessage.js`):REACT_APP_MICROSERVICES_URL=http://localhost:6001

```javascriptREACT_APP_EDITOR_URL=http://localhost:6080

import React from 'react';```

import ChartDisplay from './ChartDisplay';

import DataTable from './DataTable';### Custom Styling

import DownloadButtons from './DownloadButtons';

Override default styles in `src/custom.css`:

function BotMessage({ message }) {

  const { text, custom } = message;```css

/* Example: Change primary color */

  return (:root {

    <div className="message bot-message">  --primary-color: #007bff;

      <div className="message-content">  --secondary-color: #6c757d;

        {text}}

      </div>```

      

      {custom && (### API Integration

        <div className="message-extras">

          {/* Display chart if available */}Frontend connects to multiple backend services:

          {custom.chart_url && (

            <ChartDisplay url={custom.chart_url} />| Service | Port | Purpose |

          )}|---------|------|---------|

 | Rasa | 5005 | Conversational AI | 

          {/* Display data table if available */}| File Server | 8080 | Artifacts & training |

          {custom.data && (| Microservices | 6001 | Analytics & sensors |

            <DataTable data={custom.data} />| Editor | 6080 | File management |

          )}

          All API calls use:

          {/* Display statistics if available */}- **Credentials**: `include` (cookies)

          {custom.statistics && (- **Content-Type**: `application/json`

            <div className="statistics">- **CORS**: Enabled on all services

              <h4>Statistics</h4>

              <ul>## Next Steps

                <li>Mean: {custom.statistics.mean.toFixed(2)}</li>

                <li>Median: {custom.statistics.median.toFixed(2)}</li>- [Backend Services Documentation](./backend_services.md)

                <li>Std Dev: {custom.statistics.std.toFixed(2)}</li>- [Multi-Building Guide](./multi_building.md)

                <li>Min: {custom.statistics.min.toFixed(2)}</li>- [T5 Training Guide](./t5_training_guide.md)

                <li>Max: {custom.statistics.max.toFixed(2)}</li>- [API Reference](./api_reference.md)

              </ul>
            </div>
          )}
          
          {/* Download buttons */}
          {(custom.csv_url || custom.json_url) && (
            <DownloadButtons 
              csvUrl={custom.csv_url} 
              jsonUrl={custom.json_url} 
            />
          )}
        </div>
      )}
      
      <div className="message-time">
        {new Date().toLocaleTimeString()}
      </div>
    </div>
  );
}

export default BotMessage;
```

---

## Visualization Display

### Chart Display

**Component** (`src/components/ChartDisplay.js`):
```javascript
import React, { useState } from 'react';

function ChartDisplay({ url }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const handleLoad = () => setLoading(false);
  const handleError = () => {
    setLoading(false);
    setError(true);
  };

  return (
    <div className="chart-display">
      {loading && <div className="chart-loader">Loading chart...</div>}
      {error && <div className="chart-error">Failed to load chart</div>}
      <img
        src={url}
        alt="Data visualization"
        onLoad={handleLoad}
        onError={handleError}
        style={{ display: loading || error ? 'none' : 'block' }}
      />
    </div>
  );
}

export default ChartDisplay;
```
{% endraw %}

**CSS** (`src/styles/ChartDisplay.css`):
```css
.chart-display {
  margin: 16px 0;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.chart-display img {
  width: 100%;
  height: auto;
  display: block;
}

.chart-loader,
.chart-error {
  padding: 20px;
  text-align: center;
  color: #666;
}

.chart-error {
  color: #dc3545;
}
```

---

### Data Table

**Component** (`src/components/DataTable.js`):
```javascript
import React from 'react';

function DataTable({ data }) {
  if (!data || data.length === 0) return null;

  // Limit to first 100 rows for performance
  const displayData = data.slice(0, 100);
  const hasMore = data.length > 100;

  return (
    <div className="data-table-container">
      <table className="data-table">
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          {displayData.map((row, idx) => (
            <tr key={idx}>
              <td>{new Date(row.datetime).toLocaleString()}</td>
              <td>{row.reading_value.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {hasMore && (
        <div className="table-footer">
          Showing first 100 of {data.length} rows. Download full dataset.
        </div>
      )}
    </div>
  );
}

export default DataTable;
```

**CSS** (`src/styles/DataTable.css`):
```css
.data-table-container {
  margin: 16px 0;
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #ddd;
  border-radius: 8px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  padding: 10px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

.data-table th {
  background-color: #f8f9fa;
  font-weight: 600;
  position: sticky;
  top: 0;
  z-index: 10;
}

.data-table tr:hover {
  background-color: #f1f3f5;
}

.table-footer {
  padding: 10px;
  text-align: center;
  font-size: 0.875rem;
  color: #666;
  background-color: #f8f9fa;
  border-top: 1px solid #ddd;
}
```

---

### Download Buttons

**Component** (`src/components/DownloadButtons.js`):
```javascript
import React from 'react';

function DownloadButtons({ csvUrl, jsonUrl }) {
  return (
    <div className="download-buttons">
      {csvUrl && (
        <a href={csvUrl} download className="download-btn csv-btn">
          📥 Download CSV
        </a>
      )}
      {jsonUrl && (
        <a href={jsonUrl} download className="download-btn json-btn">
          📥 Download JSON
        </a>
      )}
    </div>
  );
}

export default DownloadButtons;
```

---

## Building Switcher

### Component

**File**: `src/components/BuildingSwitcher.js`

```javascript
import React from 'react';

const BUILDINGS = [
  { id: 'bldg1', name: 'Building 1 (ABACWS)', rasaUrl: 'http://localhost:5005' },
  { id: 'bldg2', name: 'Building 2 (Office)', rasaUrl: 'http://localhost:5006' },
  { id: 'bldg3', name: 'Building 3 (Data Center)', rasaUrl: 'http://localhost:5007' }
];

function BuildingSwitcher({ currentBuilding, onChange }) {
  return (
    <div className="building-switcher">
      <label htmlFor="building-select">Building:</label>
      <select
        id="building-select"
        value={currentBuilding.id}
        onChange={(e) => {
          const building = BUILDINGS.find(b => b.id === e.target.value);
          onChange(building);
        }}
      >
        {BUILDINGS.map(building => (
          <option key={building.id} value={building.id}>
            {building.name}
          </option>
        ))}
      </select>
    </div>
  );
}

export default BuildingSwitcher;
```

---

### Integration

**App Component** (`src/App.js`):
```javascript
import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import MessageList from './components/MessageList';
import MessageInput from './components/MessageInput';
import { sendMessage } from './services/rasaService';

const BUILDINGS = [
  { id: 'bldg1', name: 'Building 1 (ABACWS)', rasaUrl: 'http://localhost:5005' },
  { id: 'bldg2', name: 'Building 2 (Office)', rasaUrl: 'http://localhost:5006' },
  { id: 'bldg3', name: 'Building 3 (Data Center)', rasaUrl: 'http://localhost:5007' }
];

function App() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [building, setBuilding] = useState(BUILDINGS[0]);
  const [userId] = useState(`user_${Date.now()}`);

  // Load building from localStorage
  useEffect(() => {
    const savedBuildingId = localStorage.getItem('selectedBuilding');
    if (savedBuildingId) {
      const savedBuilding = BUILDINGS.find(b => b.id === savedBuildingId);
      if (savedBuilding) setBuilding(savedBuilding);
    }
  }, []);

  // Save building to localStorage
  const handleBuildingChange = (newBuilding) => {
    setBuilding(newBuilding);
    localStorage.setItem('selectedBuilding', newBuilding.id);
    // Optionally clear messages when switching buildings
    // setMessages([]);
  };

  const handleSendMessage = async (text) => {
    // Add user message to chat
    setMessages(prev => [...prev, { sender: 'user', text }]);
    setIsLoading(true);

    try {
      const responses = await sendMessage(building.rasaUrl, userId, text);
      
      // Add bot responses to chat
      responses.forEach(response => {
        setMessages(prev => [...prev, { sender: 'bot', ...response }]);
      });
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [...prev, {
        sender: 'bot',
        text: 'Sorry, I encountered an error. Please try again.'
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app">
      <Header
        building={building}
        onBuildingChange={handleBuildingChange}
        connectionStatus="connected"
      />
      <MessageList messages={messages} />
      <MessageInput onSend={handleSendMessage} isLoading={isLoading} />
    </div>
  );
}

export default App;
```

---

## Configuration

### Environment Variables

**File**: `.env`

```env
REACT_APP_RASA_URL_BLDG1=http://localhost:5005
REACT_APP_RASA_URL_BLDG2=http://localhost:5006
REACT_APP_RASA_URL_BLDG3=http://localhost:5007
REACT_APP_FILE_SERVER_URL=http://localhost:8080
REACT_APP_DEFAULT_BUILDING=bldg1
```

**Usage**:
```javascript
const rasaUrl = process.env.REACT_APP_RASA_URL_BLDG1;
```

---

### API Service

**File**: `src/services/rasaService.js`

```javascript
import axios from 'axios';

export async function sendMessage(rasaUrl, userId, message) {
  const endpoint = `${rasaUrl}/webhooks/rest/webhook`;
  
  const payload = {
    sender: userId,
    message: message
  };

  const response = await axios.post(endpoint, payload, {
    headers: {
      'Content-Type': 'application/json'
    },
    timeout: 30000  // 30 seconds
  });

  return response.data;
}

export async function checkHealth(rasaUrl) {
  const endpoint = `${rasaUrl}/version`;
  
  try {
    const response = await axios.get(endpoint, { timeout: 5000 });
    return response.status === 200;
  } catch {
    return false;
  }
}
```

---

## Customization

### Theme Colors

**File**: `src/styles/theme.css`

```css
:root {
  --primary-color: #007bff;
  --secondary-color: #6c757d;
  --success-color: #28a745;
  --danger-color: #dc3545;
  --warning-color: #ffc107;
  --info-color: #17a2b8;
  
  --user-message-bg: var(--primary-color);
  --bot-message-bg: #e9ecef;
  --app-bg: #f8f9fa;
  --header-bg: #343a40;
  --input-bg: white;
  
  --border-radius: 8px;
  --box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* Dark mode */
[data-theme="dark"] {
  --user-message-bg: #0056b3;
  --bot-message-bg: #495057;
  --app-bg: #212529;
  --header-bg: #1a1d20;
  --input-bg: #343a40;
  
  color: #f8f9fa;
}
```

---

### Custom Message Rendering

**Example**: Add emoji reactions

```javascript
function BotMessage({ message }) {
  const [reaction, setReaction] = useState(null);

  const handleReaction = (emoji) => {
    setReaction(emoji);
    // Optionally send feedback to backend
  };

  return (
    <div className="message bot-message">
      <div className="message-content">{message.text}</div>
      <div className="message-reactions">
        <button onClick={() => handleReaction('👍')}>👍</button>
        <button onClick={() => handleReaction('👎')}>👎</button>
        {reaction && <span>You reacted: {reaction}</span>}
      </div>
    </div>
  );
}
```

---

## Development

### Development Server

**Start**:
```powershell
npm start
```

**URL**: `http://localhost:3000`

**Hot Reload**: Enabled (changes reflect immediately)

---

### Building for Production

**Build**:
```powershell
npm run build
```

**Output**: `build/` directory

**Analyze Bundle Size**:
```powershell
npm install --save-dev webpack-bundle-analyzer
npm run build -- --stats
npx webpack-bundle-analyzer build/bundle-stats.json
```

---

### Testing

**Install Jest & React Testing Library**:
```powershell
npm install --save-dev @testing-library/react @testing-library/jest-dom jest
```

**Example Test** (`src/components/UserMessage.test.js`):
```javascript
import { render, screen } from '@testing-library/react';
import UserMessage from './UserMessage';

test('renders user message text', () => {
  render(<UserMessage text="Hello, OntoBot!" />);
  expect(screen.getByText('Hello, OntoBot!')).toBeInTheDocument();
});

test('applies user message styling', () => {
  const { container } = render(<UserMessage text="Test" />);
  expect(container.firstChild).toHaveClass('user-message');
});
```

**Run Tests**:
```powershell
npm test
```

---

### Debugging

**React DevTools**: Install browser extension

**Console Logging**:
```javascript
useEffect(() => {
  console.log('Messages updated:', messages);
}, [messages]);
```

**Network Inspection**: Use browser DevTools Network tab to inspect Rasa requests/responses

---

## Related Documentation

- **[Usage Guide](usage.md)**: Query examples and workflows
- **[API Reference](api_reference.md)**: REST endpoint documentation
- **[Data Payloads](data_payloads.md)**: Message format specifications
- **[Troubleshooting](troubleshooting.md)**: Common issues & solutions

---

**Frontend UI** - Beautiful, responsive chat interface for OntoBot. 💬🎨✨
