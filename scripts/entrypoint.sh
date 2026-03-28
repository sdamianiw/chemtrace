#!/bin/bash
set -e

OLLAMA_URL="${OLLAMA_BASE_URL:-http://ollama:11434}"
MODEL="${OLLAMA_MODEL:-llama3.2:3b}"

# Wait for Ollama to be ready (backup check, compose healthcheck should handle this)
echo "Checking Ollama at $OLLAMA_URL..."
python -c "
import requests, time, sys
url = '$OLLAMA_URL'
for i in range(30):
    try:
        r = requests.get(f'{url}/api/tags', timeout=3)
        if r.status_code == 200:
            print('Ollama is ready.')
            sys.exit(0)
    except Exception:
        pass
    time.sleep(2)
print('ERROR: Ollama not reachable after 60s.', file=sys.stderr)
sys.exit(1)
"

# Pull model if not already available
python -c "
import requests, json, sys
url = '$OLLAMA_URL'
model = '$MODEL'
tags = requests.get(f'{url}/api/tags').json()
names = [m['name'] for m in tags.get('models', [])]
if model in names:
    print(f'Model {model} already available.')
else:
    print(f'Pulling {model}... (this may take several minutes on first run)')
    r = requests.post(f'{url}/api/pull', json={'name': model, 'stream': False}, timeout=600)
    if r.status_code == 200:
        print(f'Model {model} ready.')
    else:
        print(f'ERROR: Failed to pull {model}: {r.text}', file=sys.stderr)
        sys.exit(1)
"

# Execute the chemtrace command
exec python -m chemtrace "$@"
