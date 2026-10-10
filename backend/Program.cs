// SPDX-License-Identifier: GPL-3.0-only
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using AssetRipper.Assets;
using AssetRipper.Assets.Collections;
using AssetRipper.Assets.Bundles;
using AssetRipper.Export.PrimaryContent;
using AssetRipper.Export.Configuration;
using AssetRipper.Export.Modules.Models;
using AssetRipper.Export.Modules.Textures;
using AssetRipper.Import.AssetCreation;
using AssetRipper.Import.Configuration;
using AssetRipper.Import.Logging;
using AssetRipper.Import.Structure;
using AssetRipper.IO.Files;
using AssetRipper.IO.Files.SerializedFiles;
using AssetRipper.SourceGenerated.Classes.ClassID_43;
using AssetRipper.SourceGenerated.Classes.ClassID_189;
using AssetRipper.SourceGenerated.Classes.ClassID_83;
using AssetRipper.SourceGenerated.Classes.ClassID_114;
using AssetRipper.SourceGenerated.Classes.ClassID_3;
using AssetRipper.Export.Modules.Audio;
using AssetRipper.SourceGenerated.Extensions;

namespace EfficientUnityRipper;

internal static class Program
{
    public const string UpstreamCommit = "beeb50ee1c223e856c860caa338e5309404956a3";
    public const int BackendRevision = 2;
    public static void Emit(object value) => Console.WriteLine(JsonSerializer.Serialize(value));
    public static string Hash(string value) => Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(value)));
    public static void AtomicJson(string path, object value)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path))!);
        string temp = path + ".tmp";
        File.WriteAllText(temp, JsonSerializer.Serialize(value), new UTF8Encoding(false));
        File.Move(temp, path, true);
    }
    static int Main(string[] args)
    {
        CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
        // Upstream libraries may write text; reserve stdout strictly for the protocol.
        TextWriter protocol = Console.Out;
        Console.SetOut(Console.Error);
        using Engine engine = new(protocol);
        if (args.Length == 2 && args[0] == "fixture")
        {
            Fixture.Create(args[1]);
            return 0;
        }
        string? line;
        while ((line = Console.ReadLine()) != null)
        {
            try
            {
                JsonNode request = JsonNode.Parse(line) ?? throw new ArgumentException("Empty request");
                engine.Handle(request);
            }
            catch (Exception ex) { engine.Send(new { kind = "error", message = ex.ToString() }); }
        }
        return 0;
    }
}

internal sealed class Engine : IDisposable, ILogger
{
    private readonly TextWriter output;
    private GameStructure? game;
    private string[] inputPaths = [];
    private readonly Dictionary<string, IUnityObjectBase> assets = new();
    private readonly Dictionary<AssetCollection, string> collections = new();
    private readonly List<string> warnings = new();
    public Engine(TextWriter output)
    {
        this.output = output;
        Logger.Add(this);
        Logger.OnStatusChanged += Status;
    }
    public void Send(object data) { output.WriteLine(JsonSerializer.Serialize(data)); output.Flush(); }
    public void Log(LogType type, LogCategory category, string message)
    {
        if (type is LogType.Error or LogType.Warning) warnings.Add($"{type}: {message}");
        Send(new { kind = "log", level = type.ToString(), category = category.ToString(), message });
    }
    public void BlankLine(int numLines) { }
    private void Status(string status, object? context) => Send(new { kind = "phase", message = status });
    private string Id(IUnityObjectBase asset) => collections[asset.Collection] + ":" + asset.PathID.ToString(CultureInfo.InvariantCulture);
    public void Handle(JsonNode request)
    {
        switch (request["command"]?.GetValue<string>())
        {
            case "scan": Scan(request); break;
            case "export": Export(request); break;
            case "ping": Send(new { kind = "ready", engine = "AssetRipper", version = "2.0.0", commit = Program.UpstreamCommit }); break;
            default: throw new ArgumentException("Unknown command");
        }
    }
    private void Scan(JsonNode request)
    {
        string[] paths = request["paths"]!.AsArray().Select(p => Path.GetFullPath(p!.GetValue<string>())).ToArray();
        if (paths.Length == 0 || paths.Any(p => !File.Exists(p) && !Directory.Exists(p))) throw new ArgumentException("Input not found");
        string destination = Path.GetFullPath(request["output"]!.GetValue<string>());
        CheckOutput(paths, destination);
        inputPaths = paths;
        string? cacheToken = request["fingerprint"]?.GetValue<string>();
        // Index contains original serialized data, without upstream processing that mutates assets.
        game?.Dispose(); game = null; assets.Clear(); collections.Clear(); warnings.Clear();
        Send(new { kind = "phase", message = "AssetRipper loading Unity files (indeterminate)" });
        game = GameStructure.Load(paths, LocalFileSystem.Instance, new CoreConfiguration());
        if (!game.IsValid) throw new InvalidDataException("AssetRipper found no valid asset collections");
        var collectionList = game.FileCollection.FetchAssetCollections().ToList();
        var identities = new HashSet<string>();
        foreach (var col in collectionList)
        {
            var names = new List<string>();
            for (Bundle? bundle = col.Bundle; bundle != null; bundle = bundle.Parent) names.Add(bundle.Name);
            names.Reverse();
            string locator = string.Join("/", names) + "/" + col.Name;
            string id = Program.Hash(locator);
            if (!identities.Add(id)) throw new InvalidDataException("Ambiguous collection identity: " + locator);
            collections[col] = id;
        }
        foreach (var asset in game.FileCollection.FetchAssets()) assets.Add(Id(asset), asset);
        Directory.CreateDirectory(Path.Combine(destination, "objects"));
        var index = new List<object>();
        int done = 0, failed = 0;
        foreach ((string id, var asset) in assets.OrderBy(p => p.Key, StringComparer.Ordinal))
        {
            Send(new { kind = "phase", message = $"Decoding {asset.ClassName}: {asset.GetBestName()} ({asset.PathID})" });
            string objectPath = Path.Combine(destination, "objects", Program.Hash(id) + ".json");
            if (cacheToken != null && File.Exists(objectPath) && File.Exists(objectPath + ".sha256"))
            {
                try
                {
                    string checksum = Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(objectPath)));
                    JsonNode cached = JsonNode.Parse(File.ReadAllText(objectPath))!;
                    if (File.ReadAllText(objectPath + ".sha256") == checksum && cached["backend_revision"]?.GetValue<int>() == Program.BackendRevision && cached["cache_token"]?.GetValue<string>() == cacheToken && cached["id"]?.GetValue<string>() == id && cached["provenance"]?["commit"]?.GetValue<string>() == Program.UpstreamCommit)
                    {
                        index.Add(new { id, name = asset.GetBestName(), class_id = asset.ClassID, type = asset.ClassName, collection = collections[asset.Collection], collection_name = asset.Collection.Name, path_id = asset.PathID.ToString(), status = cached["status"]!.GetValue<string>(), object_file = "objects/" + Path.GetFileName(objectPath) });
                        Send(new { kind = "progress", completed = ++done, total = assets.Count, message = "Checkpoint: " + asset.GetBestName() });
                        continue;
                    }
                }
                catch (Exception) { /* Corrupt checkpoint is rebuilt from source. */ }
            }
            string state = asset.Collection is SerializedAssetCollection ? "recovered" : "derived";
            if (state == "recovered" && warnings.Any(w => w.StartsWith("Error:"))) state = "partial";
            string? error = null;
            JsonNode? properties = null;
            try
            {
                using StringWriter writer = new(CultureInfo.InvariantCulture);
                var walker = new SafeJsonWalker(writer);
                if (asset.Collection.Flags.IsRelease()) asset.WalkRelease(walker); else asset.WalkEditor(walker);
                properties = JsonNode.Parse(writer.ToString());
                if (asset is RawDataObject) state = "unavailable";
                if (asset is IMonoBehaviour behaviour && behaviour.Structure == null) state = "partial";
            }
            catch (Exception ex) { state = "unavailable"; error = ex.Message; failed++; }
            var dependencies = new List<object>();
            try
            {
                // FetchDependencies hangs on Unity 6 NavMeshSettings in SourceGenerated 1.4.0.
                // Read the same recovered PPtr fields from the completed serialized walk instead.
                foreach ((string field, int fileId, long pathId) in Pointers(properties))
                {
                    if (pathId == 0) continue;
                    var dependency = fileId >= 0 && fileId < asset.Collection.Dependencies.Count ? asset.Collection.Dependencies[fileId] : null;
                    IUnityObjectBase? target = null;
                    dependency?.Assets.TryGetValue(pathId, out target);
                    dependencies.Add(new { field, file_id = fileId, path_id = pathId.ToString(), target = target == null ? null : Id(target), status = target == null || target is RawDataObject ? "unavailable" : target.Collection is SerializedAssetCollection ? "recovered" : "derived" });
                }
            }
            catch (Exception ex) { state = "partial"; error = ex.Message; failed++; }
            bool mono = asset.ClassID == 114;
            string? rawFile = null;
            if (asset is RawDataObject raw)
            {
                rawFile = "objects/" + Program.Hash(id) + ".bin";
                File.WriteAllBytes(Path.Combine(destination, rawFile), raw.RawData);
            }
            Program.AtomicJson(objectPath, new
            {
                schema_version = 1, backend_revision = Program.BackendRevision, id, cache_token = cacheToken, name = asset.GetBestName(), class_id = asset.ClassID,
                type = asset.ClassName, status = state, properties, dependencies, error,
                provenance = new { engine = "AssetRipper", commit = Program.UpstreamCommit, collection = collections[asset.Collection], collection_name = asset.Collection.Name, bundle = asset.Collection.Bundle.Name, path_id = asset.PathID.ToString(), unity_version = asset.Collection.Version.ToString(), source = asset.Collection is SerializedAssetCollection ? "serialized input via WalkRelease/WalkEditor" : "AssetRipper injected engine placeholder; not recovered from input", representation = asset.GetType().FullName, properties_status = state },
                limitations = mono ? new[] { "Serialized fields only when type layout is available; defaults may remain after import errors. Script logic is unavailable in this manifest." } : Array.Empty<string>(),
                original_path = asset.OriginalPath, raw_file = rawFile,
                classification = new { recovered = "Decoded serialized fields only", derived = "Engine-injected objects, decoded media, hierarchy projections", inferred = "None; no gameplay or shader inference is performed", unavailable = "Missing data, unsupported assets, script logic, executable shaders" }
            });
            File.WriteAllText(objectPath + ".sha256", Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(objectPath))));
            index.Add(new { id, name = asset.GetBestName(), class_id = asset.ClassID, type = asset.ClassName, collection = collections[asset.Collection], collection_name = asset.Collection.Name, path_id = asset.PathID.ToString(), status = state, object_file = "objects/" + Path.GetFileName(objectPath) });
            Send(new { kind = "progress", completed = ++done, total = assets.Count, message = asset.GetBestName() });
        }
        var manifest = new
        {
            schema_version = 1, backend_revision = Program.BackendRevision, engine = "AssetRipper", engine_version = "2.0.0", engine_commit = Program.UpstreamCommit,
            created_utc = DateTime.UtcNow, sources = paths, assets = index,
            collections = collectionList.Select(c => new { id = collections[c], name = c.Name, bundle = c.Bundle.Name, origin = c is SerializedAssetCollection ? "serialized_input" : "engine_injected", kind = c.Any(a => a is ILevelGameManager) ? "scene" : "asset_collection", kind_status = "derived", unity_version = c.Version.ToString(), dependencies = c.Dependencies.Select(d => d == null ? null : collections.GetValueOrDefault(d)).ToArray() }),
            warnings, failed, limitations = new[] { "No automatic 1:1 reconstruction. Imported fields can be incomplete: consult warnings and representation.", "No script logic recovery or executable shader recovery is claimed. Hierarchy/dependency projections are derived from serialized references." }
        };
        Program.AtomicJson(Path.Combine(destination, "manifest.json"), manifest);
        Send(new { kind = "complete", operation = "scan", manifest = Path.Combine(destination, "manifest.json"), count = assets.Count, failed });
    }
    private static IEnumerable<(string field, int fileId, long pathId)> Pointers(JsonNode? node, string path = "")
    {
        if (node is JsonObject obj)
        {
            if (obj["m_FileID"] is JsonValue file && obj["m_PathID"] is JsonValue id)
            {
                yield return (path, file.GetValue<int>(), id.GetValue<long>());
            }
            else foreach ((string name, JsonNode? value) in obj)
                foreach (var pointer in Pointers(value, path.Length == 0 ? name : path + "." + name)) yield return pointer;
        }
        else if (node is JsonArray array)
            for (int i = 0; i < array.Count; i++)
                foreach (var pointer in Pointers(array[i], path + "[" + i + "]")) yield return pointer;
    }
    private void Export(JsonNode request)
    {
        if (game == null) throw new InvalidOperationException("Scan input first to load engine");
        string directory = Path.GetFullPath(request["output"]!.GetValue<string>());
        CheckOutput(inputPaths, directory);
        Directory.CreateDirectory(directory);
        string format = request["format"]?.GetValue<string>() ?? "media";
        var ids = request["ids"]!.AsArray().Select(n => n!.GetValue<string>()).ToArray();
        var results = new List<object>();
        int done = 0, errors = 0;
        foreach (string id in ids)
        {
            try
            {
                if (!assets.TryGetValue(id, out var asset)) throw new KeyNotFoundException(id);
                string stem = Program.Hash(id);
                string path;
                using MemoryStream stream = new();
                if (asset is IMesh mesh && format is "media" or "glb")
                {
                    if (!MeshData.TryMakeFromMesh(mesh, out var data) || data.Vertices.Length == 0 || data.ProcessedIndexBuffer.Length == 0) throw new InvalidDataException("Mesh has no decoded geometry");
                    var scene = GlbMeshBuilder.Build(mesh);
                    if (!GlbWriter.TryWrite(scene, stream, out string? error)) throw new InvalidDataException(error);
                    path = Path.Combine(directory, stem + ".glb");
                }
                else if (asset is IImageTexture texture && format is "media" or "png")
                {
                    if (!TextureConverter.TryConvertToBitmap(texture, out var bitmap) || bitmap.IsEmpty) throw new InvalidDataException("Texture could not be decoded");
                    bitmap.Save(stream, ImageExportFormat.Png);
                    path = Path.Combine(directory, stem + ".png");
                }
                else if (asset is IAudioClip audio && format == "media")
                {
                    if (!AudioClipDecoder.TryDecode(audio, out byte[]? bytes, out string? extension, out _)) throw new InvalidDataException("Audio could not be decoded");
                    stream.Write(bytes!); path = Path.Combine(directory, stem + "." + extension);
                }
                else throw new NotSupportedException("Decoded media export unavailable for " + asset.ClassName + "; serialized JSON remains available");
                if (stream.Length == 0) throw new InvalidDataException("Empty media");
                // Exclusive output: never overwrite user data.
                using (FileStream file = new(path, FileMode.CreateNew)) { stream.Position = 0; stream.CopyTo(file); }
                results.Add(new { id, name = asset.GetBestName(), path, status = "derived", bytes = stream.Length });
            }
            catch (Exception ex) { errors++; results.Add(new { id, status = "unavailable", error = ex.Message }); }
            Send(new { kind = "progress", completed = ++done, total = ids.Length, message = id });
            Program.AtomicJson(Path.Combine(directory, "export-results.json"), results);
        }
        Program.AtomicJson(Path.Combine(directory, "export-results.json"), results);
        Send(new { kind = "complete", operation = "export", results, failed = errors });
    }
    public void Dispose() { game?.Dispose(); Logger.Remove(this); Logger.OnStatusChanged -= Status; }
    private static void CheckOutput(string[] paths, string output)
    {
        foreach (string input in paths)
        {
            string root = Directory.Exists(input) ? input : Path.GetDirectoryName(input)!;
            if (output.Equals(root, StringComparison.OrdinalIgnoreCase) || output.StartsWith(root.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                throw new ArgumentException("Output must be outside the input installation");
        }
    }
}

internal sealed class SafeJsonWalker(TextWriter writer) : DefaultJsonWalker(writer)
{
    public override void VisitPrimitive<T>(T value)
    {
        if (value is float f && !float.IsFinite(f)) Writer.Write(JsonSerializer.Serialize(f.ToString(CultureInfo.InvariantCulture)));
        else if (value is double d && !double.IsFinite(d)) Writer.Write(JsonSerializer.Serialize(d.ToString(CultureInfo.InvariantCulture)));
        else base.VisitPrimitive(value);
    }
}
