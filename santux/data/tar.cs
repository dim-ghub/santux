// Minimal stand-in for Windows' tar.exe (bsdtar), which Wine doesn't ship. The GTAVXR Suite
// runs "C:\windows\system32\tar.exe -x -f <archive> -C <dest>" to unpack every .zip / .oiv
// mod it imports; without it the import fails with "Windows tar.exe not found".
// Supports only that: extracting a zip-format archive (.zip, .oiv) into an existing folder.
// Like bsdtar without -P, it refuses entries with absolute paths or ".." outside dest.
using System;
using System.IO;
using System.IO.Compression;

static class Tar {
    static int Fail(string msg) { Console.Error.WriteLine("tar: " + msg); return 1; }

    static int Main(string[] args) {
        bool extract = false; string file = null, dir = ".";
        for (int i = 0; i < args.Length; i++) {
            string a = args[i];
            if (a == "-f" || a == "-C") {
                if (i + 1 >= args.Length) return Fail("option " + a + " needs an argument");
                if (a == "-f") file = args[++i]; else dir = args[++i];
            } else if (a.StartsWith("-") && a.Length > 1) {
                foreach (char c in a.Substring(1)) {
                    if (c == 'x') extract = true;
                    else if (c == 'f') { if (i + 1 >= args.Length) return Fail("option -f needs an argument"); file = args[++i]; }
                    else if (c == 'v') { }
                    else return Fail("unsupported option -" + c + " (this tar.exe only extracts zip archives)");
                }
            } else return Fail("unexpected argument: " + a);
        }
        if (!extract || file == null) return Fail("usage: tar -x -f <archive.zip> [-C <dir>]");
        if (!File.Exists(file)) return Fail(file + ": cannot open");
        if (!Directory.Exists(dir)) return Fail(dir + ": no such directory");

        string root = Path.GetFullPath(dir).TrimEnd('\\', '/') + Path.DirectorySeparatorChar;
        try {
            using (var zip = ZipFile.OpenRead(file)) {
                foreach (var e in zip.Entries) {
                    string target = Path.GetFullPath(Path.Combine(root, e.FullName));
                    if (Path.IsPathRooted(e.FullName) || !target.StartsWith(root, StringComparison.OrdinalIgnoreCase))
                        return Fail(e.FullName + ": path outside the destination, refusing");
                    if (e.FullName.EndsWith("/") || e.FullName.EndsWith("\\")) { Directory.CreateDirectory(target); continue; }
                    Directory.CreateDirectory(Path.GetDirectoryName(target));
                    e.ExtractToFile(target, true);
                }
            }
        } catch (InvalidDataException) {
            return Fail(file + ": not a zip archive. This tar.exe only handles .zip/.oiv; extract RAR or 7z "
                        + "archives on Linux and import the extracted folder instead");
        } catch (Exception ex) {
            return Fail(file + ": " + ex.Message);
        }
        return 0;
    }
}
