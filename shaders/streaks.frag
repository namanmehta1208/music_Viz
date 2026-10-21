#version 330

// renderer.py rewrites this number to match NUM_BANDS in visualizer.py
#define NUM_BANDS 32

in vec2 uv;
out vec4 fragColor;

uniform float levels[NUM_BANDS];    // smoothed loudness per band, 0..1 (bass first)
uniform float flashes[NUM_BANDS];   // flash brightness per band, 0..1
uniform vec3 palette[3];            // theme colors: centre (bass), middle, sides (treble)
uniform vec2 resolution;            // target size in pixels

// Theme color for a band: blend centre -> middle -> sides.
vec3 band_color(float t) {
    return t < 0.5 ? mix(palette[0], palette[1], t * 2.0)
                   : mix(palette[1], palette[2], (t - 0.5) * 2.0);
}

// Deterministic pseudo-random number in 0..1 for a given input.
// Same input -> same value every frame, so bars don't jump around.
float hash(float n) {
    return fract(sin(n * 127.1) * 43758.5453);
}

void main() {
    float scale = resolution.y / 480.0;   // keep proportions when the window resizes

    // Bars are centred vertically. Each one spans BASE_HALF_HEIGHT above and
    // below the middle (20%..80% of the screen), and loud hits stretch it by
    // up to STRETCH more (12%..88%). Edges are crisp, softened over ~1 px.
    const float BASE_HALF_HEIGHT = 0.30;
    const float STRETCH = 0.08;
    float from_middle = abs(uv.y - 0.5);
    if (from_middle > BASE_HALF_HEIGHT + STRETCH) {   // above/below every bar
        fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }
    float edge = 1.0 / resolution.y;
    // Slightly brighter toward the bottom, like the reference.
    float shade = mix(1.0, 0.75, clamp(uv.y, 0.0, 1.0));

    // Mirrored layout: distance from the screen centre picks the band
    // (bass near the middle, treble toward the sides). Each side gets its own
    // random nudges so the two halves are similar but not identical.
    float side = uv.x < 0.5 ? 0.0 : 1.0;
    float from_centre = abs(uv.x - 0.5) * resolution.x;   // pixels
    float half_screen = 0.5 * resolution.x;

    vec3 color = vec3(0.0);
    for (int i = 0; i < NUM_BANDS; ++i) {
        float level = levels[i];
        float flash = flashes[i];
        if (flash <= 0.002) continue;      // not flashing: bar is fully off

        float seed = float(i) + side * 101.0;
        float slot = (float(i) + 0.5 + (hash(seed) - 0.5) * 0.8) / float(NUM_BANDS);
        float position = mix(0.02, 0.88, slot) * half_screen;
        float dx = from_centre - position;

        // Bars are thin by default. Only some slots (about 1 in 3) can turn
        // into wide bars, and only while they flash hard.
        float can_widen = step(0.65, hash(seed + 13.0));
        float half_width = (0.8 + hash(seed + 7.0) * 1.4
                           + can_widen * 7.0 * flash * flash) * scale;
        float core = 1.0 - smoothstep(half_width - 0.8, half_width + 0.8, abs(dx));
        if (core <= 0.0) continue;         // this pixel is not on this bar

        // This bar's height: taller when the band is loud and flashing hard.
        float half_height = BASE_HALF_HEIGHT + STRETCH * flash * level;
        core *= smoothstep(half_height + edge, half_height - edge, from_middle);

        // Brightness comes only from the flash: no flash, no bar. Loud
        // (sustained) bands flash a bit brighter.
        float energy = flash * (3.6 + 1.2 * level);

        // Theme color, burning toward white in the core of a strong flash
        // (like an overexposed light), so hits read as hot and bright.
        vec3 tint = band_color(float(i) / float(NUM_BANDS - 1));
        tint = mix(tint, vec3(1.0), flash * flash * core * 0.15);

        color += core * energy * tint;
    }

    fragColor = vec4(color * shade, 1.0);
}
