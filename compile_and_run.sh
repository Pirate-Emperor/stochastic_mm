#!/bin/bash

# Script pour compiler et exécuter le projet

# Couleurs pour les messages
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Compilation du projet ===${NC}"

# Nettoyer et recréer le dossier build
echo -e "${BLUE}Nettoyage du build précédent...${NC}"
rm -rf build
mkdir -p build
cd build

# Configurer avec CMake
echo -e "${BLUE}Configuration avec CMake...${NC}"
cmake ..
if [ $? -ne 0 ]; then
    echo -e "${RED}Erreur lors de la configuration CMake${NC}"
    exit 1
fi

# Compiler
echo -e "${BLUE}Compilation...${NC}"
cmake --build . --parallel
if [ $? -ne 0 ]; then
    echo -e "${RED}Erreur lors de la compilation${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Compilation réussie${NC}"
echo -e "${BLUE}=== Exécution du programme ===${NC}\n"

# Exécuter
./market_engine

echo -e "\n${GREEN}✓ Programme terminé${NC}"


