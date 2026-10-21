// Helpers shared by the shaders. A shader with an include line for this file
// gets it pasted in at that spot (by load_fragment() in base.py).

// Pattern-free random number for a point (Dave Hoskins' "hash without sine").
// The usual sin()-based one shows faint diagonal lines at some positions.
float hash(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

// Smooth random hills: random values on a grid, blended between.
float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

// Noise at several sizes added together: big soft shapes with finer detail.
float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    for (int i = 0; i < 4; ++i) {
        value += amplitude * noise(p);
        p = p * 2.03 + 17.0;
        amplitude *= 0.5;
    }
    return value;
}

// Last step for the calm visualizations: soft tone mapping (bright light
// never clips), gamma, and a tiny noise so dark gradients don't show
// color banding.
vec3 finish(vec3 color, float exposure, float time) {
    color = vec3(1.0) - exp(-color * exposure);
    color = pow(max(color, 0.0), vec3(1.0 / 2.2));
    return color + (hash(gl_FragCoord.xy + floor(fract(time) * 977.0)) - 0.5) / 255.0;
}
