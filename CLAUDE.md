# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI-powered debate coaching chatbot built with Streamlit that helps students structure their arguments effectively. The app uses Upstage Solar Pro 2 for coaching feedback and Perplexity API for real-time fact-checking with web search capabilities.

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application locally
streamlit run app.py

# Run with custom port
streamlit run app.py --server.port 8502

# Run in development container (auto-configured)
streamlit run app.py --server.enableCORS false --server.enableXsrfProtection false
```

## Required API Keys

Configure these in Streamlit Cloud secrets or environment variables:
- `UPSTAGE_API_KEY`: For Solar Pro 2 coaching and Groundedness Check
- `PERPLEXITY_API_KEY`: For web-based fact-checking

## Architecture & Key Components

### Core Files
- `app.py`: Main application with coaching logic, fact-checking, and UI
- `requirements.txt`: Python dependencies (streamlit, openai>=1.52.2, requests)
- `.devcontainer/devcontainer.json`: Development container configuration for GitHub Codespaces

### Key Functions & Logic

**API Client Initialization (app.py:89-115)**
- `init_clients()`: Initializes both Upstage and Perplexity OpenAI clients
- Supports fallback to environment variables if Streamlit secrets not available
- Returns dictionary of available clients

**Argument Structure Analysis (app.py:123-182)**
- `analyze_argument_structure()`: Pattern-based detection of claims, evidence, and reinforcement
- Identifies source citations using "~에 따르면" patterns
- Returns structured analysis for coaching feedback

**Fact-Checking System (app.py:184-278)**
- `perplexity_fact_check()`: Uses Perplexity for real-time web search
- Combines web search results with Upstage Groundedness Check
- Returns confidence scores, search results, and source URLs
- Falls back to Perplexity-only verification if Upstage unavailable

**Coaching Feedback (app.py:280-335)**
- `generate_coaching_feedback()`: Creates structured feedback using Solar Pro 2
- Analyzes argument structure and provides improvement suggestions
- Includes examples of improved arguments
- Uses encouraging tone with specific actionable advice

### UI Components

- Argument structure visualization with color-coded boxes (claim, evidence, reinforcement)
- Progress indicators showing argument completeness
- Fact-check results with confidence scores and source links
- Coaching feedback in expandable sections
- Topic selection with example templates

## Important Implementation Details

1. **Dual Model Integration**: Uses Solar Pro 2 for coaching and Perplexity for fact-checking
2. **Real-time Web Search**: Perplexity provides current information for fact verification
3. **Groundedness Validation**: Combines web search with Upstage's Groundedness Check for accuracy
4. **Pattern Recognition**: Detects Korean debate patterns for structure analysis
5. **Progressive Coaching**: Tracks argument components and provides targeted improvement suggestions

## Testing Considerations

When testing the coaching chatbot:
- Test with various debate topics in Korean
- Verify fact-checking with different source citation formats
- Test API fallback behavior when keys are missing
- Validate argument structure detection accuracy
- Check coaching feedback quality and relevance