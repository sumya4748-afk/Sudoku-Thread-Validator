SUDOKU VALIDATION — WINDOWS DELIVERY STATUS

IMPORTANT: This ZIP contains the full source project and an automated GitHub Actions Windows build workflow. It does NOT contain a prebuilt Windows .exe.

For a Windows no-install demo:
1. Upload the contents of this folder to a GitHub repository (including .github/workflows/windows-release.yml).
2. On GitHub open Actions > Build Windows standalone Sudoku > Run workflow.
3. After a successful run, download the SudokuValidation_Windows_Ready artifact.
4. Extract the artifact ZIP and then SudokuValidation_Windows_Ready.zip.
5. Open SudokuValidation/SudokuValidation.exe. No Python/GCC needed on the demo PC.

The Windows workflow must succeed before treating the app as tested on Windows. The native executable has NOT been compiled or executed in this Linux environment.

Local macOS/Linux: use the existing START_MAC.command / START_LINUX.sh with their documented prerequisites.

Linux verification on this source: gcc build; 6 Python bridge tests PASS; 1859 shell tests PASS, 0 FAIL; sanitizer checks skipped.
