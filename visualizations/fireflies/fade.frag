#version 330

// Dims what was drawn last frame (blended as "keep alpha of it"), so moving
// fireflies leave short, fading trails instead of being cleared every frame.

in vec2 uv;
out vec4 fragColor;

uniform float keep;   // fraction of the light to keep, 0..1

void main() {
    fragColor = vec4(0.0, 0.0, 0.0, keep);
}
