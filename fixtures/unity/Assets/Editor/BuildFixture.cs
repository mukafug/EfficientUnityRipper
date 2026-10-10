// SPDX-License-Identifier: GPL-3.0-only
using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.Animations;
using UnityEngine;
using UnityEngine.SceneManagement;
public static class BuildFixture
{
    public static void Build()
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene);
        var root = new GameObject("Authored Root");
        var child = new GameObject("Authored Triangle"); child.transform.SetParent(root.transform);
        child.transform.localPosition = new Vector3(1,2,3); child.transform.localScale = new Vector3(2,2,2);
        var mesh = new Mesh { name="Authored Triangle Mesh" };
        mesh.vertices = new[] { Vector3.zero, Vector3.right, Vector3.up };
        mesh.triangles = new[] { 0,1,2 }; mesh.uv = new[] { Vector2.zero, Vector2.right, Vector2.up };
        mesh.RecalculateNormals(); mesh.RecalculateBounds(); AssetDatabase.CreateAsset(mesh,"Assets/triangle.asset");
        var tex = new Texture2D(4,4,TextureFormat.RGBA32,false) { name="Authored Checker" };
        var pixels = new Color[16]; for(int i=0;i<16;i++) pixels[i] = (i+i/4)%2 == 0 ? Color.cyan : Color.magenta;
        tex.SetPixels(pixels); tex.Apply(); AssetDatabase.CreateAsset(tex,"Assets/checker.asset");
        var mat = new Material(Shader.Find("EfficientUnityRipper/Fixture")) { name="Authored Material" };
        mat.mainTexture=tex; mat.color=new Color(.4f,.7f,.9f,1); AssetDatabase.CreateAsset(mat,"Assets/material.mat");
        child.AddComponent<MeshFilter>().sharedMesh=mesh; child.AddComponent<MeshRenderer>().sharedMaterial=mat;
        var collider=child.AddComponent<BoxCollider>(); collider.size=new Vector3(2,3,4);
        var body=child.AddComponent<Rigidbody>(); body.mass=3.5f; body.useGravity=false;
        var light=root.AddComponent<Light>(); light.intensity=2.5f; light.range=8;
        var config=ScriptableObject.CreateInstance<FixtureConfig>(); config.name="Authored Mechanics Config"; config.icon=tex;
        AssetDatabase.CreateAsset(config,"Assets/config.asset");
        var mechanics=child.AddComponent<FixtureMechanics>(); mechanics.target=root; mechanics.material=mat; mechanics.config=config;
        var clip=new AnimationClip { name="Authored Motion" }; clip.SetCurve("",typeof(Transform),"m_LocalPosition.x",AnimationCurve.Linear(0,1,1,2));
        AssetDatabase.CreateAsset(clip,"Assets/motion.anim");
        var controller=AnimatorController.CreateAnimatorControllerAtPath("Assets/fixture.controller"); controller.AddParameter("Speed",AnimatorControllerParameterType.Float);
        controller.AddMotion(clip); child.AddComponent<Animator>().runtimeAnimatorController=controller;
        var rig=new GameObject("Authored Bone"); rig.transform.SetParent(child.transform);
        var skinObject=new GameObject("Authored Skin"); skinObject.transform.SetParent(root.transform);
        var skinMesh=UnityEngine.Object.Instantiate(mesh); skinMesh.name="Authored Skinned Mesh";
        skinMesh.boneWeights=new[] { new BoneWeight{boneIndex0=0,weight0=1},new BoneWeight{boneIndex0=0,weight0=1},new BoneWeight{boneIndex0=0,weight0=1} };
        skinMesh.bindposes=new[] { rig.transform.worldToLocalMatrix * skinObject.transform.localToWorldMatrix }; AssetDatabase.CreateAsset(skinMesh,"Assets/skin.asset");
        var skin=skinObject.AddComponent<SkinnedMeshRenderer>(); skin.sharedMesh=skinMesh; skin.bones=new[]{rig.transform}; skin.rootBone=rig.transform; skin.sharedMaterial=mat;
        var canvas=new GameObject("Authored Canvas",typeof(RectTransform),typeof(Canvas)); canvas.transform.SetParent(root.transform);
        var ui=new GameObject("Authored UI Rect",typeof(RectTransform)); ui.transform.SetParent(canvas.transform);
        var rect=ui.GetComponent<RectTransform>(); rect.anchoredPosition=new Vector2(16,32); rect.sizeDelta=new Vector2(128,64);
        var terrainData=new TerrainData { heightmapResolution=33,size=new Vector3(10,2,10) }; var heights=new float[33,33]; heights[16,16]=.5f; terrainData.SetHeights(0,0,heights); AssetDatabase.CreateAsset(terrainData,"Assets/terrain.asset");
        Terrain.CreateTerrainGameObject(terrainData).transform.SetParent(root.transform);
        // Authored PCM WAV; no external sounds.
        using(var file=new BinaryWriter(File.Create("Assets/tone.wav"))) {
            int samples=800; file.Write(System.Text.Encoding.ASCII.GetBytes("RIFF"));file.Write(36+samples*2);file.Write(System.Text.Encoding.ASCII.GetBytes("WAVEfmt "));file.Write(16);file.Write((short)1);file.Write((short)1);file.Write(8000);file.Write(16000);file.Write((short)2);file.Write((short)16);file.Write(System.Text.Encoding.ASCII.GetBytes("data"));file.Write(samples*2);for(int i=0;i<samples;i++)file.Write((short)(Math.Sin(i*2*Math.PI*440/8000)*8000));
        }
        AssetDatabase.Refresh(); root.AddComponent<AudioSource>().clip=AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/tone.wav");
        PrefabUtility.SaveAsPrefabAsset(root,"Assets/fixture.prefab");
        EditorSceneManager.SaveScene(scene,"Assets/fixture.unity"); AssetDatabase.SaveAssets();
        string output=Environment.GetEnvironmentVariable("EUR_FIXTURE_OUTPUT"); if(string.IsNullOrEmpty(output))throw new Exception("EUR_FIXTURE_OUTPUT required");
        Directory.CreateDirectory(output);
        var builds = new[] { new AssetBundleBuild { assetBundleName="fixture-scene",assetNames=new[]{"Assets/fixture.unity"} },new AssetBundleBuild {assetBundleName="fixture-assets",assetNames=new[]{"Assets/fixture.prefab","Assets/config.asset","Assets/triangle.asset","Assets/skin.asset","Assets/checker.asset","Assets/material.mat","Assets/fixture.controller","Assets/motion.anim","Assets/terrain.asset","Assets/tone.wav"}} };
        var manifest=BuildPipeline.BuildAssetBundles(output,builds,BuildAssetBundleOptions.UncompressedAssetBundle,BuildTarget.StandaloneWindows64);
        if(manifest==null)throw new Exception("Fixture bundle build failed");
        Debug.Log("EUR fixture built: "+output);
    }
}
