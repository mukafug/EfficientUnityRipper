// SPDX-License-Identifier: GPL-3.0-only
using AssetRipper.Assets;
using AssetRipper.Primitives;
using BuildTarget = AssetRipper.IO.Files.BuildTarget;
using AssetRipper.Assets.Bundles;
using AssetRipper.Assets.IO.Writing;
using AssetRipper.IO.Endian;
using AssetRipper.IO.Files;
using AssetRipper.IO.Files.SerializedFiles;
using AssetRipper.IO.Files.SerializedFiles.Parser;
using AssetRipper.SourceGenerated;
using AssetRipper.SourceGenerated.Classes.ClassID_1;
using AssetRipper.SourceGenerated.Classes.ClassID_4;
using AssetRipper.SourceGenerated.Classes.ClassID_28;
using AssetRipper.SourceGenerated.Classes.ClassID_21;
using AssetRipper.SourceGenerated.Classes.ClassID_108;
using AssetRipper.SourceGenerated.Classes.ClassID_65;
using AssetRipper.SourceGenerated.Extensions;
using AssetRipper.SourceGenerated.Enums;

namespace EfficientUnityRipper;

internal static class Fixture
{
    public static void Create(string output)
    {
        // Entirely authored synthetic Unity serialized file; no game/Unity editor assets.
        UnityVersion version = new(2019, 4, 0, UnityVersionType.Final, 1);
        GameBundle bundle = new();
        var col = bundle.AddNewProcessedCollection("level0", version);
        col.SetLayout(version, BuildTarget.StandaloneWin64Player, TransferInstructionFlags.SerializeGameRelease);
        T Make<T>(int classId) where T : IUnityObjectBase => (T)col.CreateAsset(classId, info => AssetFactory.CreateSerialized(info, version)!);
        var root = Make<IGameObject>(1); root.Name = "Synthetic Root"; root.SetIsActive(true);
        var rootTransform = Make<ITransform>(4);
        rootTransform.GameObject_C4.SetAsset(col, root); root.AddComponent(ClassIDType.Transform, rootTransform);
        rootTransform.LocalScale_C4.SetValues(1, 1, 1); rootTransform.LocalRotation_C4.W = 1;
        var child = Make<IGameObject>(1); child.Name = "Test Child"; child.SetIsActive(true);
        var childTransform = Make<ITransform>(4);
        childTransform.GameObject_C4.SetAsset(col, child); child.AddComponent(ClassIDType.Transform, childTransform);
        childTransform.Father_C4.SetAsset(col, rootTransform); rootTransform.Children_C4.AddNew().SetAsset(col, childTransform);
        childTransform.LocalPosition_C4.SetValues(1, 2, 3); childTransform.LocalScale_C4.SetValues(2, 2, 2); childTransform.LocalRotation_C4.W = 1;
        var light = Make<ILight>(108); light.GameObject_C8.SetAsset(col, child); light.Intensity = 2.5f; light.Range = 8;
        child.AddComponent(ClassIDType.Light, light);
        var collider = Make<IBoxCollider>(65); collider.GameObject_C56.SetAsset(col, child); collider.Size.SetValues(2, 3, 4);
        child.AddComponent(ClassIDType.BoxCollider, collider);
        var texture = Make<ITexture2D>(28); texture.Name = "Authored Checker";
        texture.Width_C28 = 2; texture.Height_C28 = 2; texture.Format_C28 = (int)TextureFormat.RGBA32;
        texture.MipCount_C28 = 1; texture.ImageCount_C28 = 1; texture.CompleteImageSize_C28_Int32 = 16;
        texture.ImageData_C28 = [255,0,0,255, 0,255,0,255, 0,0,255,255, 255,255,255,255];
        var material = Make<IMaterial>(21); material.Name = "Authored Material";
        SerializedFileBuilder builder = new() { Generation = FormatVersion.StoresTypeDependencies, Version = version, Platform = BuildTarget.StandaloneWin64Player, EndianType = EndianType.LittleEndian, HasTypeTree = false, UserInformation = "EfficientUnityRipper synthetic GPL-3.0-only fixture" };
        foreach (var asset in col)
        {
            var type = new SerializedType { TypeID = asset.ClassID, ScriptTypeIndex = -1 };
            int typeIndex = builder.Types.Count; builder.Types.Add(type);
            using MemoryStream stream = new();
            using (AssetWriter writer = new(stream, col)) { asset.WriteRelease(writer); writer.Flush(); }
            builder.Objects.Add(new ObjectInfo(type) { FileID = asset.PathID, SerializedTypeIndex = typeIndex, ObjectData = stream.ToArray() });
        }
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(output))!);
        using FileStream file = new(output, FileMode.CreateNew);
        builder.Build().Write(file);
    }
}
