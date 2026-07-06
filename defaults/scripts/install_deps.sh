#!/usr/bin/env bash
function install(){ 
    echo "==================================="
    echo "  Dependecy installation starting"
    echo "  Do not navigate away please..."
    echo "==================================="
    #recusively find all install_deps.sh files and execute them
    find ./scripts/Extensions -type f -name "install_deps.sh" -exec bash {} \;
    find ~/homebrew/data/SkullKey/scripts/Extensions -type f -name "install_deps.sh" -exec bash {} \;



    echo "==================================="
    echo "  Dependecy installation complete"
    echo "==================================="
}

function uninstall(){
    echo "==================================="
    echo "  Dependecy uninstallation starting"
    echo "  Do not navigate away please..."
    echo "==================================="
    #recusively find all install_deps.sh files and execute them
    echo "Uninstalling dependencies - built-in extensions"
    find ./scripts/Extensions -type f -name "install_deps.sh" -exec bash {} uninstall \;
    echo "Uninstalling dependencies - user extensions"
    find ~/homebrew/data/SkullKey/scripts/Extensions -type f -name "install_deps.sh" -exec bash {} uninstall \;

    echo "==================================="
    echo "  Dependecy uninstallation complete"
    echo "==================================="
}

function ensure(){
    # Boot-time auto-provision: install ONLY the missing store deps, quietly.
    # Scoped to GOG + Amazon — their deps are small self-contained venvs, safe to
    # install unattended. Epic's heavier flatpak deps stay manual (deps button).
    echo "==================================="
    echo "  Ensuring store dependencies (GOG, Amazon)"
    echo "==================================="
    for ext in GOG Amazon; do
        script="./scripts/Extensions/${ext}/install_deps.sh"
        [ -f "$script" ] || script="${HOME}/homebrew/data/SkullKey/scripts/Extensions/${ext}/install_deps.sh"
        [ -f "$script" ] || { echo "  ${ext}: install_deps.sh not found, skipping"; continue; }
        if bash "$script" check; then
            echo "  ${ext}: dependencies already present ✓"
        else
            echo "  ${ext}: dependencies missing → installing"
            bash "$script"
        fi
    done
    echo "==================================="
    echo "  Dependency ensure complete"
    echo "==================================="
}

if [ "$1" == "uninstall" ]; then
    echo "Uninstalling dependencies"
    uninstall
elif [ "$1" == "ensure" ]; then
    ensure
else
    echo "Installing dependencies"
    install
fi