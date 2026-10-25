"""Shared GLSL snippets. Each generated shader file inlines what it needs so every .glsl in the vault
is standalone (no #include tooling required)."""

HEADER = """// ---------------------------------------------------------------------------
// Project-TheCreator · {name}
// {desc}
// Convention: three.js ShaderMaterial (built-ins: position, normal, uv, modelMatrix,
// viewMatrix, projectionMatrix, cameraPosition). Classic GLSL (varying / texture2D /
// gl_FragColor) - three.js maps these to GLSL ES 3.00 automatically.
// ---------------------------------------------------------------------------
"""

COMMON_FRAG = """
uniform vec3  uLightDir;
uniform vec3  uLightColor;
uniform float uTime;
uniform float uExposure;

float hash13(vec3 p) {
  p = fract(p * 0.1031);
  p += dot(p, p.zyx + 31.32);
  return fract((p.x + p.y) * p.z);
}

// Procedural studio environment: sky gradient, warm ground bounce, two softboxes.
vec3 envColor(vec3 d) {
  float h = d.y;
  vec3 sky = mix(vec3(0.16, 0.19, 0.27), vec3(0.58, 0.70, 0.90), smoothstep(-0.05, 0.85, h));
  vec3 gnd = mix(vec3(0.05, 0.045, 0.04), vec3(0.20, 0.18, 0.17), smoothstep(-1.0, 0.0, h));
  vec3 c = h > 0.0 ? sky : gnd;
  c += vec3(2.4, 2.3, 2.1) * pow(max(dot(d, normalize(vec3(0.55, 0.75, 0.35))), 0.0), 48.0);
  c += vec3(0.8, 0.95, 1.3) * pow(max(dot(d, normalize(vec3(-0.7, 0.25, -0.55))), 0.0), 18.0);
  return c;
}

// Derivative-based tangent frame: normal maps without precomputed tangents.
vec3 perturbNormal(vec3 N, vec3 P, vec2 uv, vec3 mapN, float strength) {
  vec3 dp1 = dFdx(P), dp2 = dFdy(P);
  vec2 duv1 = dFdx(uv), duv2 = dFdy(uv);
  vec3 dp2perp = cross(dp2, N), dp1perp = cross(N, dp1);
  vec3 T = dp2perp * duv1.x + dp1perp * duv2.x;
  vec3 B = dp2perp * duv1.y + dp1perp * duv2.y;
  float invmax = inversesqrt(max(max(dot(T, T), dot(B, B)), 1e-12));
  mapN.xy *= strength;
  return normalize(mat3(T * invmax, B * invmax, N) * mapN);
}

vec3 tonemap(vec3 c) {
  c *= uExposure;
  c = (c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14);   // ACES fit
  return pow(clamp(c, 0.0, 1.0), vec3(1.0 / 2.2));
}
"""


def shader(name, desc, body, frag=True):
    return HEADER.format(name=name, desc=desc) + (COMMON_FRAG if frag else "") + body
