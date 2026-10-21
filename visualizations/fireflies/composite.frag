#version 330

// Final pass: night background + the fireflies (with their trails).

in vec2 uv;
out vec4 fragColor;

uniform sampler2D scene;   // fireflies and trails (HDR)
uniform vec3 background;   // theme's night color
uniform float energy;      // overall loudness, slow, 0..1
uniform float time;

#include "common.glsl"

void main() {
    // A little lighter toward the bottom, like a meadow under a night sky,
    // with slow faint mist drifting through.
    float mist = fbm(vec2(uv.x * 2.5 + time * 0.02, uv.y * 4.0 - time * 0.01));
    vec3 color = background * (mix(1.0, 0.3, uv.y) + mist * 0.8 * smoothstep(0.7, 0.0, uv.y));
    color *= 0.8 + 0.4 * energy;

    color += texture(scene, uv).rgb;

    vec2 q = (uv - 0.5) * vec2(0.8, 1.1);
    color *= 1.0 - dot(q, q) * 0.6;

    fragColor = vec4(finish(color, 1.5, time), 1.0);
}
