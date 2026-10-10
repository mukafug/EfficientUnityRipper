// SPDX-License-Identifier: GPL-3.0-only
using UnityEngine;
public class FixtureMechanics : MonoBehaviour
{
    public float moveSpeed = 4.25f;
    public int lives = 7;
    public string action = "fixture-only";
    public GameObject target;
    public Material material;
    public Vector3 checkpoint = new Vector3(3, 4, 5);
    public FixtureConfig config;
}
