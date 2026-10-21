#version 330

// Northern lights over a still mountain lake. Everything the music touches
// is smoothed on the CPU first, so nothing here ever jumps or flashes.

// load_fragment() in base.py rewrites this number to match NUM_BANDS in visualizer.py
#define NUM_BANDS 32

in vec2 uv;
out vec4 fragColor;

uniform float levels[NUM_BANDS];  // slowly smoothed loudness per band, 0..1
uniform sampler2D columns;        // per-column curtain and mountain shapes (columns.frag)
uniform vec3 palette[4];          // curtain edge, curtain body, curtain top, night sky
uniform vec2 resolution;          // target size in pixels
uniform float time;               // real seconds: stars and water move at a steady pace
uniform float energy;             // overall loudness, slow, 0..1
uniform float swell;              // slow rise and fall after bass hits, 0..1
uniform float treble;             // treble loudness, slow, 0..1

const float HORIZON = 0.24;       // water line, as a fraction of the height (also in columns.frag)
const float REFLECT_STRETCH = 2.4;

#include "common.glsl"

// Band level at t (0 = bass, 1 = treble), blended between neighbouring bands.
float level_at(float t) {
    float f = clamp(t, 0.0, 1.0) * float(NUM_BANDS - 1);
    int i = int(f);
    int j = min(i + 1, NUM_BANDS - 1);
    return mix(levels[i], levels[j], fract(f));
}

// Theme color up a curtain: bright edge -> body -> top.
vec3 curtain_color(float t) {
    return t < 0.5 ? mix(palette[0], palette[1], t * 2.0)
                   : mix(palette[1], palette[2], (t - 0.5) * 2.0);
}

// Precomputed values for column p.x, row 0..3 (see columns.frag).
vec4 column(float x, int row) {
    return texture(columns, vec2(x, (float(row) + 0.5) / 4.0));
}

// One curtain of light; k picks the layer. Its edge, rays and folds come
// from the column pre-pass.
vec3 curtain(vec2 p, int k) {
    vec4 shape = column(p.x, k);   // edge height, rays, folds
    float d = p.y - shape.x;       // > 0 above the edge

    // Music raises the curtain: bass in the middle, treble toward the sides.
    float level = level_at(abs(p.x - 0.5) * 2.0);
    float height = 0.08 + 0.32 * level + 0.08 * swell;

    // Crisp at the bottom, fading softly upward, like real aurora.
    float profile = d < 0.0 ? exp(-d * d / 0.00012)
                            : exp(-d / height) + 0.6 * exp(-d / 0.012);

    vec3 color = curtain_color(clamp(d / (height * 1.5), 0.0, 1.0));
    return color * profile * (0.3 + 0.7 * shape.y) * shape.z;
}

// A few twinkling stars on a grid of ~14 px cells, most cells empty.
float stars(vec2 p) {
    vec2 grid = p * resolution / 14.0;
    vec2 cell = floor(grid);
    float h = hash(cell);
    if (h < 0.93) return 0.0;
    vec2 spot = vec2(hash(cell + 3.1), hash(cell + 7.7)) * 0.8 + 0.1;
    float spark = smoothstep(0.14, 0.0, length(fract(grid) - spot));
    float twinkle = 0.6 + 0.4 * sin(time * (0.8 + 2.5 * hash(cell + 1.3)) + h * 40.0);
    return spark * twinkle * (h - 0.93) / 0.07;
}

// Everything above the water: sky, stars, aurora, mountains.
vec3 sky(vec2 p) {
    float up = (p.y - HORIZON) / (1.0 - HORIZON);   // 0 at the horizon, 1 at the top

    vec3 color = palette[3] * mix(0.4, 0.08, up);    // a little lighter near the horizon
    color += stars(p) * (0.4 + 1.6 * treble) * smoothstep(0.05, 0.3, up);

    float glow = (0.3 + 1.1 * energy) * (1.0 + 0.4 * swell);
    color += (curtain(p, 0) * 1.0
            + curtain(p, 1) * 0.55
            + curtain(p, 2) * 0.3) * glow;

    // Mountain silhouette sitting on the water line, faintly lit by the sky.
    float ridge = column(p.x, 3).x;
    float edge = 1.5 / resolution.y;
    float mountain = smoothstep(ridge + edge, ridge - edge, p.y);
    return mix(color, palette[3] * 0.08, mountain);
}

void main() {
    vec3 color;
    if (uv.y >= HORIZON) {
        color = sky(uv);
    } else {
        // The lake: the sky mirrored, broken up by slow horizontal ripples.
        // Ripples get bigger toward the viewer (bottom) and grow after kicks.
        // The reflection is stretched (REFLECT_STRETCH) so the shallow lake
        // still shows the curtains high above it.
        float near = (HORIZON - uv.y) / HORIZON;      // 0 at the water line, 1 at the bottom
        float wave = noise(vec2(uv.x * 3.0 + time * 0.05,
                                2.0 / (HORIZON - uv.y + 0.02) + time * 0.6));
        float wobble = (wave - 0.5) * (0.004 + 0.025 * near) * (1.0 + 1.5 * swell);
        vec2 mirrored = vec2(uv.x + wobble, HORIZON + (HORIZON - uv.y) * REFLECT_STRETCH);
        color = sky(mirrored) * mix(0.7, 0.35, near);
    }

    // Gentle vignette.
    vec2 q = (uv - 0.5) * vec2(0.8, 1.1);
    color *= 1.0 - dot(q, q) * 0.6;

    fragColor = vec4(finish(color, 1.4, time), 1.0);
}
