#!/bin/bash

if [ -z "$1" ]; then
  echo "Usage: $0 <new-version>"
  exit 1
fi

VERSION=$1

sed -i '' "s/version = \".*\"/version = \"$VERSION\"/" agentcook/pyproject.toml
sed -i '' "s/<version>.*<\/version>/<version>$VERSION<\/version>/" agentcook-java/pom.xml
sed -i '' "s/\"version\": \".*\"/\"version\": \"$VERSION\"/" agentcook-admin/package.json
sed -i '' "s/\"version\": \".*\"/\"version\": \"$VERSION\"/" agentcook-app/package.json
sed -i '' "s/appVersion: .*/appVersion: $VERSION/" deploy/helm/agentcook/Chart.yaml

echo "Successfully bumped version to $VERSION"
