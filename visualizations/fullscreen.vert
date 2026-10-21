#version 330

// Every pass draws one rectangle covering the whole target.
// The rectangle's corners come from renderer.py; we just pass uv along.
in vec2 in_position;   // corner in clip space: -1..1
in vec2 in_uv;         // corner in texture space: 0..1

out vec2 uv;

void main() {
    uv = in_uv;
    gl_Position = vec4(in_position, 0.0, 1.0);
}
