#version 460 core
#include <flutter/runtime_effect.glsl>

uniform vec2 uSize;
uniform float uTime;
uniform vec2 uTouch;   // 0..1 in screen space
uniform float uPress;  // 0..1 touch strength
uniform vec2 uTilt;    // -1..1
uniform float uCalm;   // 0 lively .. 1 calm (keyboard open)

out vec4 fragColor;

// Brand palette: ink base, blue, violet, teal, coral, warm paper highlight.
const vec3 INK = vec3(0.027, 0.031, 0.047);
const vec3 BLUE = vec3(0.102, 0.451, 0.910);
const vec3 VIOLET = vec3(0.576, 0.204, 0.902);
const vec3 TEAL = vec3(0.071, 0.620, 0.686);
const vec3 CORAL = vec3(0.910, 0.376, 0.298);
const vec3 PAPER = vec3(0.925, 0.922, 0.906);

float blob(vec2 p, vec2 c, float r) {
  vec2 d = p - c;
  return r * r / (dot(d, d) + 0.004);
}

void main() {
  vec2 frag = FlutterFragCoord().xy;
  vec2 uv = frag / uSize;
  float asp = uSize.x / uSize.y;
  vec2 p = vec2((uv.x - 0.5) * asp, uv.y - 0.5);
  float t = uTime * mix(1.0, 0.35, uCalm);

  // Slow liquid domain warp keeps the field flowing instead of orbiting.
  vec2 w = p;
  w += 0.07 * vec2(sin(p.y * 3.1 + t * 0.7), cos(p.x * 2.7 - t * 0.6));
  w += 0.035 * vec2(sin(p.y * 7.0 - t * 1.1 + uTilt.x), cos(p.x * 6.0 + t * 0.9 + uTilt.y));

  vec2 tl = uTilt * 0.06;
  vec2 c1 = vec2(-0.30 * asp + 0.18 * sin(t * 0.50), -0.28 + 0.20 * cos(t * 0.43)) + tl;
  vec2 c2 = vec2(0.28 * asp + 0.16 * cos(t * 0.37 + 1.0), -0.10 + 0.24 * sin(t * 0.52)) - tl * 1.4;
  vec2 c3 = vec2(-0.05 * asp + 0.22 * sin(t * 0.33 + 2.0), 0.22 + 0.18 * cos(t * 0.47 + 1.0)) + tl * 0.6;
  vec2 c4 = vec2(0.32 * asp + 0.14 * cos(t * 0.61), 0.34 + 0.12 * sin(t * 0.39)) - tl;
  vec2 c5 = vec2(-0.34 * asp + 0.12 * sin(t * 0.44 + 3.0), 0.40 + 0.10 * cos(t * 0.58));

  // Touch attracts the blobs: a soft, brighter blob under the finger plus a pull on the field.
  vec2 tp = vec2((uTouch.x - 0.5) * asp, uTouch.y - 0.5);
  vec2 pull = (tp - w) * uPress * 0.10 / (length(tp - w) + 0.25);
  w += pull;

  float b1 = blob(w, c1, 0.20);
  float b2 = blob(w, c2, 0.19);
  float b3 = blob(w, c3, 0.17);
  float b4 = blob(w, c4, 0.14);
  float b5 = blob(w, c5, 0.12);
  float bt = blob(w, tp, 0.10) * uPress;

  float f = b1 + b2 + b3 + b4 + b5 + bt;
  vec3 col = (b1 * BLUE + b2 * VIOLET + b3 * TEAL + b4 * CORAL + b5 * BLUE + bt * PAPER) / max(f, 0.0001);

  // Metaball body: smooth threshold, glowing rim, dark ink between blobs.
  float body = smoothstep(0.55, 1.6, f);
  float rim = smoothstep(0.7, 1.0, f) * (1.0 - smoothstep(1.0, 1.6, f));
  vec3 c = mix(INK, col * 0.82, body * 0.9);
  c += col * rim * 0.45;
  c += PAPER * pow(smoothstep(1.8, 4.0, f), 2.0) * 0.18;

  // Ripples radiating from the touch.
  float d = length(w - tp);
  float ring = sin(d * 38.0 - uTime * 5.0) * exp(-d * 5.0) * uPress;
  c += PAPER * ring * 0.10;

  // Soft vignette and gentle film grain-free finish.
  float vig = smoothstep(1.15, 0.25, length(p * vec2(0.9, 1.0)));
  c *= mix(0.62, 1.0, vig);
  fragColor = vec4(c, 1.0);
}
