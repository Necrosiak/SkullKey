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
    # GOG + Amazon + Epic : small self-contained venvs, safe to install
    # unattended (Epic = legendary venv depuis le passage stand-alone ; un
    # flatpak legendary existant satisfait le check → rien n'est réinstallé).
    echo "==================================="
    echo "  Ensuring store dependencies (GOG, Amazon, Epic)"
    echo "==================================="
    local failed=0
    for ext in GOG Amazon Epic; do
        script="./scripts/Extensions/${ext}/install_deps.sh"
        [ -f "$script" ] || script="${HOME}/homebrew/data/SkullKey/scripts/Extensions/${ext}/install_deps.sh"
        [ -f "$script" ] || { echo "  ${ext}: install_deps.sh not found, skipping"; continue; }
        if bash "$script" check; then
            echo "  ${ext}: dependencies already present ✓"
        else
            echo "  ${ext}: dependencies missing → installing"
            if bash "$script" && bash "$script" check; then
                echo "  ${ext}: installation successful ✓"
            else
                echo "  ${ext}: ERROR: dependency installation failed"
                failed=1
            fi
        fi
    done
    echo "==================================="
    echo "  Dependency ensure complete"
    echo "==================================="
    return "${failed}"
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
