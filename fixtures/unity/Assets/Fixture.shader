// SPDX-License-Identifier: GPL-3.0-only
Shader "EfficientUnityRipper/Fixture" {
    Properties { _MainTex("Texture", 2D) = "white" {} _Color("Tint", Color) = (0.4,0.7,0.9,1) }
    SubShader { Pass { CGPROGRAM
        #pragma vertex vert
        #pragma fragment frag
        #include "UnityCG.cginc"
        struct appdata { float4 vertex:POSITION; float2 uv:TEXCOORD0; };
        struct v2f { float4 pos:SV_POSITION; float2 uv:TEXCOORD0; };
        sampler2D _MainTex; float4 _Color;
        v2f vert(appdata v) { v2f o; o.pos=UnityObjectToClipPos(v.vertex); o.uv=v.uv; return o; }
        fixed4 frag(v2f i):SV_Target { return tex2D(_MainTex,i.uv)*_Color; }
    ENDCG } }
}
