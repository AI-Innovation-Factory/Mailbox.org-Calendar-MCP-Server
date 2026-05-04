# CalDAV MCP Server
A Model Context Protocol (MCP) server built with Python and FastMCP. This server provides an interface for Large Language Models (LLMs) to seamlessly interact with CalDAV-compatible calendar servers.

It allows AI assistants to fetch, create, update, and delete calendar events using strict, predictable tool definitions.

## Features
- Read Events: Fetch calendar events within a specific time window.

- Create Events: Add new events, including optional recurring rules (RRULE) and participants.

- Update Events: Modify existing events, adjust schedules, and manage attendees (add/remove).

- Delete Events: Safely remove events using their unique UID.

- Built-in LLM Prompt: Includes a specific manage_calendar_instructions prompt to ensure the LLM understands formatting rules (e.g., strictly using UTC ISO 8601).

## Prerequisites
Ensure you have Python 3.x installed along with the required dependencies. You can install the dependencies using pip from requirements.txt:

```Bash
pip install -r ./requirements.txt
```
## Configuration
The server relies on environment variables for authentication and connection routing. Create a .env file in the root directory of your project with the following variables:

```
# The URL of your CalDAV server
CDURL=https://caldav.yourserver.example.com/

# Your CalDAV username/email
CDUSERNAME=your_email@example.com

# Your CalDAV password or App Password
CDPASSWORD=your_secure_password
```
## Available MCP Tools
This server exposes the following tools to the LLM via MCP:

- `getCalendarEvents`

  - Fetches all events between start_iso and end_iso.

  - Note: Expects strict UTC ISO 8601 strings.

- `createCalendarEvent`

  - Creates a new calendar event.

  - Supports summaries, descriptions, locations, participant invites, and recurring rules (e.g., FREQ=WEEKLY;COUNT=5;BYDAY=MO).

- `deleteCalendarEvent`

  - Deletes an event based on its exact uid. (The LLM is instructed to always fetch the event first to guarantee the correct UID is used).

- `updateCalendarEvent`

  - Updates an existing event's details (time, summary, description, location, recurrence).

  - Can append new participant emails or remove specific attendees.

## Available Prompts
- `manage_calendar_instructions`

  - A built-in prompt that guides the LLM on how to properly use the tools. It enforces rules like never guessing the uid, always querying events first before mutating them, and utilizing proper UTC ISO 8601 timestamps.

## Running the Server
Start the server using standard Python execution. The server defaults to Server-Sent Events (SSE) transport.

```Bash
python calDavMCP.py
```

When the server starts, it will output Starting mcp server... and begin listening for MCP connections.