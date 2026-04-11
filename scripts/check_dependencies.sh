#!/bin/bash
# Pre-flight dependency check for Meta2Data.
# Can be run directly, or sourced by an entry script which then calls
# meta2data_check_dependencies.
#
# Exits (or returns when sourced) non-zero if any required binary, QIIME2
# plugin, or Python package is missing. Prints a report with install hints.

# Required non-QIIME2 binaries that install_binaries.sh provisions.
_M2D_VENDOR_BINARIES=(
    vsearch
    fastp
)

# Required generic system utilities (expected on any Linux distro).
_M2D_SYSTEM_BINARIES=(
    python3
    wget
    curl
    unzip
    tar
    gzip
    md5sum
    awk
    sed
    grep
    find
)

# Required QIIME2 plugins. Names match the strings `qiime info` prints.
_M2D_QIIME_PLUGINS=(
    cutadapt
    dada2
    demux
    feature-classifier
    feature-table
    fragment-insertion
    quality-filter
    rescript
    vsearch
)

# Python packages NOT auto-provided by QIIME2 (biopython) plus a sanity
# check on ones that ARE (pandas/numpy/requests/biom-format) to catch a
# broken QIIME2 install.
#
# Each entry is "import_name:pip_name".
_M2D_PYTHON_PACKAGES=(
    "Bio:biopython"
    "pandas:pandas"
    "numpy:numpy"
    "requests:requests"
    "biom:biom-format"
)

_m2d_missing_vendor=()
_m2d_missing_system=()
_m2d_missing_qiime=()
_m2d_missing_python=()

_m2d_check_binary() {
    command -v "$1" >/dev/null 2>&1
}

_m2d_check_python_package() {
    python3 -c "import $1" >/dev/null 2>&1
}

# Collect QIIME2 plugin list once and grep locally — avoids launching
# `qiime <plugin> --help` N times (each spawn costs ~1s).
_m2d_load_qiime_plugin_list() {
    if ! command -v qiime >/dev/null 2>&1; then
        _M2D_QIIME_INFO=""
        return 1
    fi
    _M2D_QIIME_INFO=$(qiime info 2>&1 || true)
    return 0
}

_m2d_check_qiime_plugin() {
    grep -qE "^[[:space:]]*$1:[[:space:]]" <<<"$_M2D_QIIME_INFO"
}

meta2data_check_dependencies() {
    _m2d_missing_vendor=()
    _m2d_missing_system=()
    _m2d_missing_qiime=()
    _m2d_missing_python=()

    for bin in "${_M2D_VENDOR_BINARIES[@]}"; do
        _m2d_check_binary "$bin" || _m2d_missing_vendor+=("$bin")
    done

    for bin in "${_M2D_SYSTEM_BINARIES[@]}"; do
        _m2d_check_binary "$bin" || _m2d_missing_system+=("$bin")
    done

    if command -v qiime >/dev/null 2>&1; then
        _m2d_load_qiime_plugin_list || true
        for plugin in "${_M2D_QIIME_PLUGINS[@]}"; do
            _m2d_check_qiime_plugin "$plugin" || _m2d_missing_qiime+=("$plugin")
        done
    else
        _m2d_missing_qiime=("${_M2D_QIIME_PLUGINS[@]}")
        _m2d_missing_system+=("qiime")
    fi

    for entry in "${_M2D_PYTHON_PACKAGES[@]}"; do
        local import_name="${entry%%:*}"
        local pip_name="${entry##*:}"
        if command -v python3 >/dev/null 2>&1; then
            _m2d_check_python_package "$import_name" || _m2d_missing_python+=("$pip_name")
        else
            _m2d_missing_python+=("$pip_name")
        fi
    done

    local total=$(( ${#_m2d_missing_vendor[@]} + ${#_m2d_missing_system[@]} + ${#_m2d_missing_qiime[@]} + ${#_m2d_missing_python[@]} ))

    if [[ $total -eq 0 ]]; then
        echo "[check] All dependencies satisfied."
        return 0
    fi

    echo ""
    echo "=============================================================="
    echo "  Meta2Data dependency check FAILED — ${total} item(s) missing"
    echo "=============================================================="

    if [[ ${#_m2d_missing_vendor[@]} -gt 0 ]]; then
        echo ""
        echo "Missing pipeline binaries:"
        for b in "${_m2d_missing_vendor[@]}"; do
            echo "  - $b"
        done
        echo "  Install: bash scripts/install_binaries.sh"
    fi

    if [[ ${#_m2d_missing_system[@]} -gt 0 ]]; then
        echo ""
        echo "Missing system utilities (should be available on any Linux distro):"
        for b in "${_m2d_missing_system[@]}"; do
            echo "  - $b"
        done
        echo "  Install via your package manager, e.g.:"
        echo "    sudo apt-get install ${_m2d_missing_system[*]}"
    fi

    if [[ ${#_m2d_missing_qiime[@]} -gt 0 ]]; then
        echo ""
        if [[ -z "${_M2D_QIIME_INFO:-}" ]]; then
            echo "QIIME2 not detected at all. Install the 2024.10 amplicon distribution"
            echo "following https://docs.qiime2.org/2024.10/install/, then activate its"
            echo "conda environment before running Meta2Data."
        else
            echo "Missing QIIME2 plugins:"
            for p in "${_m2d_missing_qiime[@]}"; do
                echo "  - $p"
            done
            echo "  Your QIIME2 env looks incomplete. Install the full amplicon"
            echo "  distribution (not just the core) per QIIME2's official docs."
        fi
    fi

    if [[ ${#_m2d_missing_python[@]} -gt 0 ]]; then
        echo ""
        echo "Missing Python packages:"
        for p in "${_m2d_missing_python[@]}"; do
            echo "  - $p"
        done
        echo "  Install with:"
        echo "    pip install ${_m2d_missing_python[*]}"
    fi

    echo ""
    echo "=============================================================="
    return 1
}

# When executed directly, run the check and exit with its status.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    meta2data_check_dependencies
    exit $?
fi
