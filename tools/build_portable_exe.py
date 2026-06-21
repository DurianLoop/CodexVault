from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def csharp_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def main() -> int:
    run_script = csharp_string(str(ROOT / "run_codex_vault.bat"))
    working_directory = csharp_string(str(ROOT))
    output_exe = str(ROOT / "CodexVault.exe")
    source = f'''
using System.Diagnostics;
public class CodexVaultLauncher {{
  public static void Main() {{
    var psi = new ProcessStartInfo();
    psi.FileName = "cmd.exe";
    psi.Arguments = "/c \\\"{run_script}\\\"";
    psi.WorkingDirectory = "{working_directory}";
    psi.UseShellExecute = false;
    Process.Start(psi);
  }}
}}
'''
    ps = (
        "$src = @'\n"
        + source
        + "\n'@; "
        "Add-Type -TypeDefinition $src -Language CSharp "
        f"-OutputAssembly '{output_exe}' -OutputType ConsoleApplication"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        cwd=ROOT,
        text=True,
    )
    exe = ROOT / "CodexVault.exe"
    if result.returncode == 0 and exe.exists():
        print(f"Built {exe}")
        return 0
    print("PowerShell Add-Type did not produce CodexVault.exe")
    return result.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
