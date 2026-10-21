#version 330

// Final pass: combine bars + glow, then add the "camera lens" look.

in vec2 uv;
out vec4 fragColor;

uniform sampler2D scene;    // sharp bars (HDR)
uniform sampler2D bloom1;   // blurred copy, 1/2 resolution (tight)
uniform sampler2D bloom2;   // blurred copy, 1/4 resolution (medium)
uniform sampler2D bloom3;   // blurred copy, 1/8 resolution (wide haze)

uniform float time;
uniform float aberration;   // RGB split at the screen's left/right edges, in pixels
uniform float exposure;     // overall brightness
uniform float energy;       // how much is flashing right now, 0..1
uniform float kick;         // bass hit strength right now, 0..1
uniform vec3 accent;        // theme accent color (light leak)

float hash1(float n) {
    return fract(sin(n * 91.345) * 43758.5453);
}

// Pattern-free random number for a pixel (Dave Hoskins' "hash without sine").
// The usual sin()-based one shows faint diagonal lines at some pixel positions.
float hash(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

// The image at point p, as a lens would show it: sharp in the middle,
// increasingly out of focus toward the left and right edges.
// Kicks pump the glow.
vec3 lens(vec2 p) {
    float defocus = smoothstep(0.12, 0.42, abs(p.x - 0.5));
    vec3 sharp = texture(scene, p).rgb;
    vec3 soft = texture(bloom1, p).rgb;
    vec3 base = mix(sharp, soft, defocus * 0.9);
    float glow = 1.0 + 1.5 * kick + 1.5 * energy;   // more flashing = more glow
    return base
         + (texture(bloom1, p).rgb * 0.10
          + texture(bloom2, p).rgb * 0.08
          + texture(bloom3, p).rgb * 0.06) * glow;
}

// A soft diagonal beam of light from the bottom-left corner that sways slowly.
vec3 light_leak(vec2 p) {
    float angle = 0.45 + 0.06 * sin(time * 0.25);
    vec2 dir = vec2(cos(angle), sin(angle));
    vec2 q = p - vec2(-0.05, 0.05);
    float along = dot(q, dir);                       // distance along the beam
    float across = dot(q, vec2(-dir.y, dir.x));      // distance from its centre line
    float beam = exp(-across * across / 0.006)
               * smoothstep(-0.05, 0.08, along) * smoothstep(0.55, 0.05, along);
    return accent * beam;
}

// Short-lived RGB flares that pop up at random spots along the screen borders:
// three thin lines (red, green, blue) slightly apart, plus a soft glow, like
// light catching the edge of a lens. Up to three can be alive at once; each
// lives for one "slot" of time, fading in and out with a little stutter.
// They only show while a kick (bass hit) is happening.
vec3 border_flares(vec2 p) {
    vec3 total = vec3(0.0);
    for (int k = 0; k < 3; ++k) {
        float fk = float(k);
        float rate = 0.9 + fk * 0.55;                  // events per second
        float clock = time * rate + fk * 0.37;
        float slot = floor(clock);
        float life = sin(fract(clock) * 3.14159);      // 0 -> 1 -> 0 over the slot

        if (hash1(slot * 3.1 + fk * 17.0) > 0.6) continue;   // most slots stay empty

        // Pick a border and a spot along it.
        float pick = hash1(slot * 7.7 + fk * 3.0);
        float d;      // distance from that border, 0 at the edge
        float along;  // position along that border
        if      (pick < 0.30) { d = p.x;       along = p.y; }   // left
        else if (pick < 0.60) { d = 1.0 - p.x; along = p.y; }   // right
        else if (pick < 0.80) { d = 1.0 - p.y; along = p.x; }   // top
        else                  { d = p.y;       along = p.x; }   // bottom

        float centre = 0.15 + 0.7 * hash1(slot * 5.3 + fk);
        float half_len = 0.06 + 0.16 * hash1(slot * 2.9 + fk * 5.0);
        float segment = smoothstep(half_len, 0.0, abs(along - centre));

        // Three thin color lines a few pixels apart, plus a soft glow behind.
        vec3 rgb = vec3(exp(-pow((d - 0.006) / 0.004, 2.0)),
                        exp(-pow((d - 0.014) / 0.005, 2.0)),
                        exp(-pow((d - 0.022) / 0.006, 2.0)));
        rgb += vec3(0.5, 0.6, 0.9) * exp(-d / 0.04) * 0.25;

        float stutter = 0.6 + 0.4 * hash1(floor(time * 24.0) + slot);
        total += rgb * segment * life * stutter;
    }
    return total * 1.8 * smoothstep(0.15, 0.6, kick);   // only on bass hits
}

void main() {
    // On strong kicks, jolt the image sideways by a hair for a frame or two.
    vec2 p = uv;
    p.x += (hash1(floor(time * 60.0)) - 0.5) * 0.006 * smoothstep(0.6, 1.0, kick);

    // Chromatic aberration: red from slightly outward, blue from slightly
    // inward, green in place. Zero at the centre and growing toward the edges,
    // so centre bars stay clean and outer bars split into rainbow fringes.
    // Kicks widen the split.
    float texel = 1.0 / float(textureSize(scene, 0).x);
    float x = 2.0 * (p.x - 0.5);                         // -1 (left) .. 1 (right)
    float shift = aberration * (1.0 + 0.8 * kick) * x * abs(x) * texel;
    vec3 color = vec3(lens(p + vec2(shift, 0.0)).r,
                      lens(p).g,
                      lens(p - vec2(shift, 0.0)).b);

    color += light_leak(uv) * (0.12 * energy + 0.1 * kick);   // only while flashing
    color += border_flares(uv);

    // Vignette: darken toward the edges, more at top and bottom.
    vec2 q = (uv - 0.5) * vec2(0.9, 1.5);
    color *= 1.0 - dot(q, q) * 0.9;

    // Tone mapping: squeeze 0..infinity brightness into 0..1 smoothly.
    // Compressing the brightest channel and scaling the others along keeps
    // the hue (bright gold stays gold instead of washing out to white).
    // A little of the per-channel version is mixed in so the hottest spots
    // still burn slightly toward white. Kicks push the exposure.
    color *= exposure * (1.0 + 0.5 * kick);
    float peak = max(max(color.r, color.g), color.b);
    vec3 hue_kept = color * ((1.0 - exp(-peak)) / max(peak, 1e-4));
    vec3 burned = vec3(1.0) - exp(-color);
    color = mix(hue_kept, burned, 0.25);

    // Black level: cut the faintest glow tails to true black. Gamma (below)
    // lifts tiny values a lot (0.002 would show as visible gray), so without
    // this the background never gets pitch black.
    const float BLACK = 0.003;
    color = max(color - BLACK, 0.0) / (1.0 - BLACK);

    // Film grain on lit areas only (scaled by brightness), so it adds texture
    // to the light without speckling the black background.
    float lit = max(max(color.r, color.g), color.b);
    color += (hash(gl_FragCoord.xy + floor(fract(time) * 977.0)) - 0.5) * 0.04 * lit;

    // Gamma: convert from linear light to what the monitor expects.
    color = pow(max(color, 0.0), vec3(1.0 / 2.2));

    fragColor = vec4(color, 1.0);
}
