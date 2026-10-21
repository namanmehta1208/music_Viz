#version 330

// Colored smoke slowly swirling in dark water.
//
// The swirl is "domain warping": look up noise at a point that has itself
// been pushed around by noise, twice over. That bends smooth noise into
// curls and wisps that look like ink in water. The bass sets how hard the
// water is stirred; each third of the spectrum feeds one ink color; strong
// kicks drop a fresh bloom of ink that spreads and gets pulled into the swirl.

in vec2 uv;
out vec4 fragColor;

#define MAX_DROPS 4

uniform vec3 palette[4];          // bass ink, mid ink, treble ink, water
uniform vec4 drops[MAX_DROPS];    // x, y (0..1), age in seconds (< 0 = none), color 0..2
uniform vec2 resolution;          // target size in pixels
uniform float time;               // real seconds
uniform float flow;               // "music time": runs faster when the music is louder
uniform float energy;             // overall loudness, slow, 0..1
uniform float bass;               // loudness of each third of the spectrum, slow, 0..1
uniform float mid;
uniform float treble;
uniform float swell;              // slow rise and fall after bass hits, 0..1

#include "common.glsl"

const float SCALE = 1.6;          // how many swirls fit on screen (bigger = smaller swirls)

void main() {
    float aspect = resolution.x / resolution.y;
    vec2 p = uv * vec2(aspect, 1.0) * SCALE;

    // Two rounds of warping, each one drifting slowly over time.
    float stir = 0.9 + 1.4 * bass + 1.0 * swell;
    vec2 q = vec2(fbm(p + vec2(0.0, flow * 0.05)),
                  fbm(p + vec2(5.2, 1.3) - flow * 0.04));
    vec2 r = vec2(fbm(p + stir * q + vec2(1.7, 9.2) + flow * 0.07),
                  fbm(p + stir * q + vec2(8.3, 2.8) - flow * 0.06));
    float f = fbm(p + stir * r);

    // Three inks, each living in a different part of the warped field, each
    // as strong as its part of the music.
    vec3 ink = palette[0] * smoothstep(0.40, 0.80, q.x) * (0.2 + 1.0 * bass)
             + palette[1] * smoothstep(0.40, 0.80, r.y) * (0.2 + 1.0 * mid)
             + palette[2] * smoothstep(0.55, 0.85, f)   * (0.2 + 1.2 * treble);
    // Thin it out into wisps, so dark water shows between them: only the
    // densest parts of the field carry ink, and their edges stay soft.
    float density = pow(smoothstep(0.50, 0.88, f), 2.0);
    vec3 color = ink * density * (0.35 + 0.8 * energy);

    // Drops: a cloud of fresh ink that grows, gets dragged by the same
    // swirl (so it curls with everything else), and fades over a few seconds.
    vec2 warped = p + 0.25 * stir * (r - 0.5);
    for (int i = 0; i < MAX_DROPS; ++i) {
        float age = drops[i].z;
        if (age < 0.0) continue;
        vec2 centre = drops[i].xy * vec2(aspect, 1.0) * SCALE;
        float radius = 0.05 + 0.22 * sqrt(age);
        vec2 d = warped - centre;
        float cloud = exp(-dot(d, d) / (radius * radius));
        float life = smoothstep(0.0, 0.4, age) * exp(-age / 3.0);
        color += palette[int(drops[i].w)] * cloud * life * smoothstep(0.3, 0.8, f) * 1.5;
    }

    // Water: very dark, a touch lighter near the top, like light from above.
    color += palette[3] * mix(0.4, 1.0, uv.y);

    vec2 v = (uv - 0.5) * vec2(0.8, 1.1);
    color *= 1.0 - dot(v, v) * 0.7;

    fragColor = vec4(finish(color, 1.3, time), 1.0);
}
