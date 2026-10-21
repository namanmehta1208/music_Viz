#version 330

// Pre-pass for aurora.frag. Everything slow to compute there (the noise
// shaping the curtains and the mountains) depends only on the horizontal
// position, so it's worked out here once per column instead of once per
// pixel. The target is one pixel per screen column and 4 rows tall:
//
//     row 0..2   curtain k: (edge height, ray brightness, fold brightness)
//     row 3      mountain ridge height

in vec2 uv;
out vec4 fragColor;

uniform vec2 resolution;   // the size of the real screen, not this target
uniform float flow;        // "music time": runs faster when the music is louder

#include "common.glsl"

const float HORIZON = 0.24;   // must match aurora.frag

void main() {
    // x in screen heights, so shapes keep their proportions in wide windows.
    float x = uv.x * resolution.x / resolution.y;
    int row = int(gl_FragCoord.y);

    if (row == 3) {
        float ridge = HORIZON + 0.01 + 0.22 * pow(fbm(vec2(x * 1.1, 4.2)), 2.0)
                    + 0.015 * fbm(vec2(x * 9.0, 1.3));
        fragColor = vec4(ridge, 0.0, 0.0, 1.0);
        return;
    }

    float k = float(row);
    // The bright bottom edge hangs along a slow, wandering wave.
    float edge = 0.50 + 0.10 * k
               + 0.08 * sin(x * (1.1 + 0.4 * k) + flow * 0.12 + k * 2.1)
               + 0.20 * (fbm(vec2(x * 0.7 + k * 7.3, flow * 0.04)) - 0.5);
    // Vertical rays drifting sideways along the curtain.
    float rays = smoothstep(0.25, 0.85,
                            fbm(vec2(x * 7.0 + k * 13.0 - flow * 0.15, flow * 0.08 + k)));
    // Folds: the curtain is brighter in some stretches than others.
    float folds = smoothstep(0.25, 0.7,
                             fbm(vec2(x * 1.3 + k * 5.0 + flow * 0.05, k * 3.0)));
    fragColor = vec4(edge, rays, folds, 1.0);
}
