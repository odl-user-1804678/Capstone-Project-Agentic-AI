#!/bin/bash

# Usage: ./push_to_github.sh "commit message"
COMMIT_MSG=$1

if [ -z "$COMMIT_MSG" ]; then
  echo "❌ Commit message is missing."
  exit 1
fi

# Go to your repo directory
cd /full/path/to/Capstone-Project-Agentic-AI || exit 1

git add index.html
git commit -m "$COMMIT_MSG"
git push origin main  # change 'main' if your branch is different

echo "✅ index.html pushed to GitHub!"
