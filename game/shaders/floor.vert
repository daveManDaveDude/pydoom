#version 120
attribute vec2 aPos;
varying vec2 vUV;
void main() {
    vUV = aPos;
    gl_Position = vec4(aPos, 0.0, 1.0);
}