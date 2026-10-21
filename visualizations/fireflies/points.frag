#version 330

// A soft dot of light: a small hot core and a wide faint halo. Drawn with
// additive blending, so overlapping fireflies add up to brighter light.

in vec3 color;
out vec4 fragColor;

void main() {
    float d = length(gl_PointCoord - 0.5) * 2.0;   // 0 centre, 1 edge
    if (d > 1.0) discard;
    float core = exp(-d * d * 40.0);
    float halo = exp(-d * d * 5.0) * (1.0 - d) * 0.3;
    fragColor = vec4(color * (core + halo), 1.0);
}
