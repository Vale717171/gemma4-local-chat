#!/bin/bash
echo ""
echo "┌─────────────────────────────────────────┐"
echo "│     Gemma 4 Chat — OpenRouter API Key   │"
echo "└─────────────────────────────────────────┘"
echo ""
echo "Incolla la tua API key OpenRouter e premi Invio:"
echo "(La key NON verrà mostrata mentre scrivi)"
echo ""
read -s -p "API Key: " api_key
echo ""

if [ -z "$api_key" ]; then
  echo "❌ Nessuna key inserita. Operazione annullata."
  exit 1
fi

CONFIG_FILE="$HOME/mlx-chat/openrouter_config.py"
echo "OPENROUTER_API_KEY = \"$api_key\"" > "$CONFIG_FILE"

echo ""
echo "✅ API key salvata in $CONFIG_FILE"
echo ""
echo "Puoi chiudere questa finestra."
