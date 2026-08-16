#!/bin/bash
# seed-content.sh - Ensures default files exist in sample-content directory

mkdir -p sample-content/assets

if [ ! -f sample-content/index.html ]; then
    echo "Creating default index.html..."
    cat << 'EOF' > sample-content/index.html
<!DOCTYPE html>
<html>
<head><title>Mini CDN Default</title></head>
<body><h1>Mini CDN Default</h1></body>
</html>
EOF
fi

if [ ! -f sample-content/assets/app.js ]; then
    echo "Creating default app.js..."
    echo 'console.log("Default script loaded");' > sample-content/assets/app.js
fi

if [ ! -f sample-content/assets/logo.png ]; then
    echo "Creating dummy logo.png..."
    echo "DUMMY PNG DATA" > sample-content/assets/logo.png
fi

echo "Sample content directories and files seeded successfully."
