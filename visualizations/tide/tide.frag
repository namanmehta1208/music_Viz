#version 330

// A few soft glowing lines along a horizon, moving like slow waves. The
// spectrum sets how tall the waves are along each line: bass in the middle,
// treble toward the sides. Each line shows the music a little later than
// the one above it, so changes ripple down through the lines.

in vec2 uv;
out vec4 fragColor;

uniform sampler2D spectra;   // one row per line, one column per band, 0..1
uniform int num_lines;
uniform vec3 palette[4];     // top line, middle lines, bottom line, background glow
uniform vec2 resolution;     // target size in pixels
uniform float time;          // real seconds
uniform float flow;          // "music time": runs faster when the music is louder
uniform float energy;        // overall loudness, slow, 0..1
uniform float swell;         // slow rise and fall after bass hits, 0..1
uniform float treble;        // treble loudness, slow, 0..1

#include "common.glsl"

const float SPACING = 0.05;  // gap between lines, as a fraction of the height

// Line k's loudness at t (0 = bass in the middle, 1 = treble at the sides).
// Sampling between texel centres blends neighbouring bands smoothly.
float level_at(int k, float t) {
    vec2 size = vec2(textureSize(spectra, 0));
    vec2 texel = vec2(t * (size.x - 1.0) + 0.5, float(k) + 0.5) / size;
    return texture(spectra, texel).r;
}

// Height of line k at horizontal position x (0..1); ax is x in screen
// heights, so the waves keep their shape in wide windows.
float line_y(int k, float x, float ax) {
    float fk = float(k);
    float base = 0.5 + (float(num_lines - 1) * 0.5 - fk) * SPACING;
    // Two slow waves travelling in opposite directions, plus a gentle drift.
    float wave = 0.6 * sin(ax * 3.0 - flow * 0.9 + fk * 0.6)
               + 0.4 * sin(ax * 5.3 + flow * 0.6 + fk * 1.3)
               + 0.8 * (noise(vec2(ax * 1.5 + fk * 3.0, flow * 0.2)) - 0.5);
    float level = level_at(k, abs(x - 0.5) * 2.0);
    float amplitude = 0.012 + 0.09 * level * (1.0 + 0.5 * swell);
    return base + wave * amplitude;
}

void main() {
    float aspect = resolution.x / resolution.y;
    float ax = uv.x * aspect;
    float px = 1.0 / resolution.y;   // one pixel, in uv units

    // Faint glow behind the lines, brighter when the music is louder.
    vec2 c = (uv - vec2(0.5)) * vec2(aspect * 0.6, 2.2);
    vec3 color = palette[3] * exp(-dot(c, c)) * (0.25 + 0.6 * energy);

    // Lines fade out toward the left and right edges.
    float ends = smoothstep(0.0, 0.18, uv.x) * smoothstep(1.0, 0.82, uv.x);

    for (int k = 0; k < num_lines; ++k) {
        float y = line_y(k, uv.x, ax);
        // Distance measured across the line (not just straight up), so the
        // line keeps the same thickness where it slopes.
        float slope = (line_y(k, uv.x + 0.002, ax + 0.002 * aspect) - y) / 0.002;
        float d = abs(uv.y - y) / sqrt(1.0 + slope * slope);

        float core = exp(-pow(d / (1.3 * px), 2.0));   // thin bright line
        float haze = exp(-d / 0.025) * 0.12;           // soft glow around it

        // Little glints sliding along the line, more with treble.
        float fk = float(k);
        float glint = pow(noise(vec2(ax * 18.0 + fk * 7.0 - flow * 2.0, fk)), 6.0)
                    * treble * 6.0;

        float level = level_at(k, abs(uv.x - 0.5) * 2.0);
        float brightness = (0.5 + 1.8 * level) * (1.0 + 0.3 * swell);

        float t = fk / float(max(num_lines - 1, 1));
        vec3 tint = t < 0.5 ? mix(palette[0], palette[1], t * 2.0)
                            : mix(palette[1], palette[2], (t - 0.5) * 2.0);
        color += tint * ((core * (1.0 + glint) + haze) * brightness * ends);
    }

    // Gentle vignette.
    vec2 q = (uv - 0.5) * vec2(0.8, 1.1);
    color *= 1.0 - dot(q, q) * 0.6;

    fragColor = vec4(finish(color, 1.3, time), 1.0);
}
