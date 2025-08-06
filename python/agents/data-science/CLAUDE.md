# ADK Data Science Multi-Agent System

## Agent OS Documentation

### Product Context
- **Mission & Vision:** @.agent-os/product/mission.md
- **Technical Architecture:** @.agent-os/product/tech-stack.md
- **Development Roadmap:** @.agent-os/product/roadmap.md
- **Decision History:** @.agent-os/product/decisions.md

### Development Standards
- **Code Style:** @~/.agent-os/standards/code-style.md
- **Best Practices:** @~/.agent-os/standards/best-practices.md

### Project Management
- **Active Specs:** @.agent-os/specs/
- **Spec Planning:** Use `@~/.agent-os/instructions/create-spec.md`
- **Tasks Execution:** Use `@~/.agent-os/instructions/execute-tasks.md`

## Workflow Instructions

When asked to work on this codebase:

1. **First**, check @.agent-os/product/roadmap.md for current priorities
2. **Then**, follow the appropriate instruction file:
   - For new features: @.agent-os/instructions/create-spec.md
   - For tasks execution: @.agent-os/instructions/execute-tasks.md
3. **Always**, adhere to the standards in the files listed above

## Important Notes

- Product-specific files in `.agent-os/product/` override any global standards
- User's specific instructions override (or amend) instructions found in `.agent-os/specs/...`
- Always adhere to established patterns, code style, and best practices documented above.

## Architecture Overview

This is a sophisticated multi-agent system built on Google's ADK framework for democratizing data science capabilities through natural language interactions.

### Component Classification
- **Core Nodes:** Root agent, BigQuery tools, database connections (require careful oversight)
- **Business Logic:** Agent coordination, query processing, prompt systems (standard development)
- **Leaf Nodes:** Export features, utilities, standalone tools (autonomous development acceptable)

### Key Capabilities
- Natural Language to SQL with CHASE-SQL integration
- Multi-project BigQuery operations with service account authentication
- Automated data analysis and visualization with Plotly
- BigQuery ML operations with RAG-enhanced documentation
- CSV export functionality through ADK web interface
- Comprehensive testing and evaluation framework
- Production deployment on Vertex AI Agent Engine (migrating to Cloud Run)