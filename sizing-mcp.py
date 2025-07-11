import math
from typing import List, Dict, Any
from fastmcp import FastMCP

# Create the MCP server
mcp = FastMCP("Hardware Sizing Calculator")

# Data about instance sizes
search_instances = {
    "S20": {
        "ram_gigs": 4,
        "storage_gigs": 80,
        "vCPU": 2,
        "price_hr": 0.16
    },
    "S30": {
        "ram_gigs": 8,
        "storage_gigs": 161,
        "vCPU": 4,
        "price_hr": 0.33
    },
    "S40": {
        "ram_gigs": 16,
        "storage_gigs": 322,
        "vCPU": 8,
        "price_hr": 0.68
    },
    "S50": {
        "ram_gigs": 32,
        "storage_gigs": 644,
        "vCPU": 16,
        "price_hr": 1.40
    },
    "S60": {
        "ram_gigs": 64,
        "storage_gigs": 1288,
        "vCPU": 32,
        "price_hr": 2.52
    },
    "S70": {
        "ram_gigs": 96,
        "storage_gigs": 1932,
        "vCPU": 48,
        "price_hr": 3.57
    },
    "S80": {
        "ram_gigs": 128,
        "storage_gigs": 2576,
        "vCPU": 64,
        "price_hr": 4.66
    }
}

@mcp.tool
def calculate_sizing_requirements(
    lexical_sizing: Dict[str, Any],
    vector_sizing: Dict[str, Any],
    reindex_space_multiplier: float = 2.25
) -> Dict[str, Any]:
    """
    Calculates estimated storage, RAM, and vCPU for a search system and suggests an instance.

    Use this tool to get hardware recommendations based on your data and query load.
    You must provide detailed configurations for both lexical and vector components.

    Args:
        lexical_sizing (Dict[str, Any]): Configuration for lexical search.
            Example:
            {
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
            }

        vector_sizing (Dict[str, Any]): Configuration for vector search.
            Example:
            {
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

        reindex_space_multiplier (float, optional): A multiplier for storage to account for reindexing. Defaults to 2.25.

    Returns:
        A dictionary with the final calculated results: StorageGb, RAMGb, vCPU, LexicalDocs, and suggested_instance.
    """

    # --- Internal Helper Functions (encapsulated within the tool) ---
    def _get_total_autocomplete_chars(field: Dict[str, Any]) -> int:
        min_grams, max_grams = field.get('min_grams', 3), field.get('max_grams', 15)
        if field.get('autocomplete_type') == 'edgeGram':
            return ((max_grams - min_grams + 1) * (max_grams + min_grams) // 2)
        elif field.get('autocomplete_type') == 'nGram':
            avg_chars = max(max_grams, field.get('avg_chars', 30))
            term1 = (avg_chars + 1) * (max_grams - min_grams + 1) * (max_grams + min_grams) // 2
            term2 = (max_grams * (max_grams + 1) * (2 * max_grams + 1)) // 6
            term3 = (min_grams * (min_grams + 1) * (2 * min_grams + 1)) // 6
            return term1 - term2 + term3 - (min_grams**2)
        raise ValueError("Unknown AutocompleteType")

    def _calculate_basic_storage(num_docs: int, fields: List[Dict[str, Any]]) -> float:
        storage = 0.0
        for field in fields:
            count, f_type = field.get('count', 1), field.get('field_type')
            if f_type == 'String':
                storage += field.get('size', 0) * field.get('storage_multiplier', 3.33) * num_docs * count
            elif f_type == 'Autocomplete':
                storage += _get_total_autocomplete_chars(field) * num_docs * count
            elif f_type == 'Embedded':
                emb_sizing = field['embedded_sizing']
                emb_storage = _calculate_basic_storage(emb_sizing.get('num_documents', 1000), emb_sizing.get('fields', []))
                storage += emb_storage * num_docs * count
        return storage

    def _calculate_embedded_docs(num_docs: int, fields: List[Dict[str, Any]]) -> int:
        added = 0
        for field in fields:
            if field.get('field_type') == 'Embedded':
                emb_sizing, count = field['embedded_sizing'], field.get('count', 1)
                direct = emb_sizing.get('num_documents', 1000) * num_docs
                recursive = _calculate_embedded_docs(direct, emb_sizing.get('fields', []))
                added += (direct + recursive) * count
        return added

    def _calculate_lexical_sizing(params: Dict[str, Any]) -> Dict[str, Any]:
        num_docs, fields = params.get('num_documents', 1000), params.get('fields', [])
        storage_bytes = _calculate_basic_storage(num_docs, fields)
        ram_denom = params.get('index_size_to_ram_ratio_denominator', 8)
        return {
            'storage_gb': storage_bytes / (1024**3),
            'ram_gb': (storage_bytes / ram_denom) / (1024**3),
            'vcpu': math.ceil(params.get('qps', 20) * params.get('latency', 0.05)),
            'lexical_docs': num_docs + _calculate_embedded_docs(num_docs, fields)
        }

    def _calculate_vector_sizing(params: Dict[str, Any]) -> Dict[str, Any]:
        num_docs = params.get('num_documents', 1000)
        base_storage = sum(f.get('dimensions', 1536) * 4 * f.get('count', 1) for f in params.get('fields', []) if f.get('field_type') == 'Vector') * num_docs
        
        q_settings = params.get('quantization_settings', {})
        q_type = q_settings.get('type', 'none')
        q_factor = {'scalar': 3.75, 'binary': 24}.get(q_type, 1.0)
        
        if q_type != 'none':
            quantized_storage = base_storage / q_factor
            ram_bytes = 1.1 * quantized_storage
            storage_bytes = (base_storage + quantized_storage) if q_settings.get('method') == 'database' else quantized_storage
        else:
            ram_bytes = base_storage * 1.1
            storage_bytes = base_storage
            
        return {
            'storage_gb': storage_bytes / (1024**3),
            'ram_gb': ram_bytes / (1024**3),
            'vcpu': math.ceil(params.get('qps', 20) * params.get('latency', 0.3))
        }

    # --- Main Execution ---
    lexical_results = _calculate_lexical_sizing(lexical_sizing)
    vector_results = _calculate_vector_sizing(vector_sizing)
    
    total_storage = (lexical_results['storage_gb'] + vector_results['storage_gb']) * reindex_space_multiplier
    total_ram = lexical_results['ram_gb'] + vector_results['ram_gb']
    total_vcpu = lexical_results['vcpu'] + vector_results['vcpu']
    
    # --- Find Suggested Instance ---
    suggested_instance = "Custom sizing required. No suitable instance found."
    for name, specs in search_instances.items():
        if (specs['ram_gigs'] >= total_ram and
            specs['vCPU'] >= total_vcpu and
            specs['storage_gigs'] >= total_storage):
            suggested_instance = name
            break  # Found the smallest suitable instance

    return {
        'StorageGb': round(total_storage, 3),
        'RAMGb': round(total_ram, 3),
        'vCPU': total_vcpu,
        'LexicalDocs': lexical_results['lexical_docs'],
        'suggested_instance': suggested_instance
    }

if __name__ == "__main__":
    print("\n🛠️  Hardware Sizing Calculator Server is running!")
    print("\nProvide the model with a detailed scenario to get a hardware estimate.")
    print("\nExample queries you can ask:")
    print("- 'Calculate hardware needs for 1M documents with 1536-dim vectors and some string fields.'")
    print("- 'I have 10 million documents, each with 5 embedded comments. What sizing do I need for high QPS?'")
    print("- 'Give me a hardware estimate for a lexical-only setup with 50M documents and heavy autocomplete usage.'")
    
    mcp.run()