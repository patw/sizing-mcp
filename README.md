# Hardware Sizing Calculator MCP

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A FastMCP-based tool for calculating Atlas search hardware requirements for both lexical and vector use cases. 

**Not an official MongoDB Product**

## Features

- Calculates estimated storage, RAM, and vCPU requirements
- Supports complex document structures including embedded documents
- Handles both lexical and vector search components
- Provides instance size recommendations based on common cloud instance types
- Interactive MCP interface for easy querying

## Installation

1. Clone the repository:
```bash
git clone https://github.com/patw/sizing-mcp.git
cd sizing-mcp
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the MCP server in claude desktop or other MCP clients with this config:
```json
{
  "mcpServers": {
    "Search Sizing Calculator": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "fastmcp, pymongo",
        "fastmcp",
        "run",
        "/Users/patw/dev/sizing-mcp/sizing-mcp.py"
      ]
    }
  }
}
```
**Be sure to change the directory where the MCP code is stored!!**


Then interact with it through any MCP client. Example queries:
- "Calculate hardware needs for 1M documents with 1536-dim vectors and some string fields"
- "What sizing do I need for 10M documents with 5 embedded comments each?"
- "Give me a hardware estimate for a lexical-only setup with 50M documents"

### Example Configuration

```json
{
  "lexical_sizing": {
    "num_documents": 1000000,
    "qps": 100,
    "latency": 0.05,
    "fields": [
      {"field_type": "String", "size": 150, "count": 2},
      {"field_type": "Autocomplete", "autocomplete_type": "edgeGram"},
      {
        "field_type": "Embedded",
        "count": 1,
        "embedded_sizing": {
          "num_documents": 5,
          "fields": [{"field_type": "String", "size": 50}]
        }
      }
    ]
  },
  "vector_sizing": {
    "num_documents": 1000000,
    "qps": 50,
    "latency": 0.2,
    "fields": [
      {"field_type": "Vector", "dimensions": 1536}
    ],
    "quantization_settings": {
      "type": "scalar",
      "method": "database"
    }
  }
}
```

## Development

Contributions are welcome! Please open an issue or pull request on GitHub.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

Pat Wendorf ([@patw](https://github.com/patw)) - pat.wendorf@mongodb.com
