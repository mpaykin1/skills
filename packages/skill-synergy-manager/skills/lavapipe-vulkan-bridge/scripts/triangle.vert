#version 450
vec2 p[3]=vec2[](vec2(-.75,-.75),vec2(.75,-.75),vec2(0,.75));
void main(){gl_Position=vec4(p[gl_VertexIndex],0,1);}
