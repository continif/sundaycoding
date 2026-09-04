# scripts/ — come si scrive uno script qui
- Shebang + `set -euo pipefail`. `source lib/common.sh`. Log su STDERR, risultato su stdout.
- Argomenti obbligatori espliciti (`${1:?}`), un `--help`, exit code che significano qualcosa.
- Una responsabilità per file. Naming verbo_oggetto.sh.
