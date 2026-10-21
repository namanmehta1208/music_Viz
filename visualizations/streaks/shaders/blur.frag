#version 330

// One direction of a Gaussian blur. Running it horizontally and then
// vertically gives a full 2D blur at a fraction of the cost.
// With direction = (0, 0) it is a plain copy, which renderer.py uses to
// shrink an image to a smaller texture.

in vec2 uv;
out vec4 fragColor;

uniform sampler2D src;
uniform vec2 direction;   // one texel step in uv units, times a spread factor

void main() {
    // 9-tap Gaussian folded into 5 lookups using linear filtering
    // (each off-centre lookup lands between two texels and averages them).
    vec3 c = texture(src, uv).rgb * 0.2270270270;
    c += texture(src, uv + direction * 1.3846153846).rgb * 0.3162162162;
    c += texture(src, uv - direction * 1.3846153846).rgb * 0.3162162162;
    c += texture(src, uv + direction * 3.2307692308).rgb * 0.0702702703;
    c += texture(src, uv - direction * 3.2307692308).rgb * 0.0702702703;
    fragColor = vec4(c, 1.0);
}
