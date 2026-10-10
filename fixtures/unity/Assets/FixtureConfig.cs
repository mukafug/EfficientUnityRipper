// SPDX-License-Identifier: GPL-3.0-only
using UnityEngine;
public class FixtureConfig : ScriptableObject
{
    public float jumpHeight = 2.75f;
    public string[] modes = { "walk", "climb" };
    public Texture2D icon;
}
