#!/usr/bin/env python3
"""Real offscreen desktop OpenGL draw and pixel readback using Mesa EGL."""
import ctypes as C
import json, os
os.environ["LIBGL_ALWAYS_SOFTWARE"]="1"
os.environ["GALLIUM_DRIVER"]="llvmpipe"
os.environ["EGL_PLATFORM"]="surfaceless"
E=C.CDLL("libEGL.so.1"); G=C.CDLL("libGL.so.1")
P=C.c_void_p; I=C.c_int; U=C.c_uint; F=C.c_float
def fn(lib,name,result,*args):
 f=getattr(lib,name);f.restype=result;f.argtypes=args;return f
def arr(*v):return (I*len(v))(*v)
get=fn(E,"eglGetDisplay",P,P)
init=fn(E,"eglInitialize",U,P,C.POINTER(I),C.POINTER(I))
bind=fn(E,"eglBindAPI",U,U)
choose=fn(E,"eglChooseConfig",U,P,C.POINTER(I),C.POINTER(P),I,C.POINTER(I))
surf=fn(E,"eglCreatePbufferSurface",P,P,P,C.POINTER(I))
ctx=fn(E,"eglCreateContext",P,P,P,P,C.POINTER(I))
make=fn(E,"eglMakeCurrent",U,P,P,P,P)
destroyc=fn(E,"eglDestroyContext",U,P,P)
destroys=fn(E,"eglDestroySurface",U,P,P)
terminate=fn(E,"eglTerminate",U,P)
d=get(None); major=I();minor=I()
assert d and init(d,C.byref(major),C.byref(minor)),"EGL init"
s=c=None
try:
 assert bind(0x30A2),"OpenGL API"
 config=P(); n=I()
 assert choose(d,arr(0x3033,1,0x3040,8,0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3038),C.byref(config),1,C.byref(n)) and n.value,"EGL config"
 s=surf(d,config,arr(0x3057,64,0x3056,64,0x3038))
 c=ctx(d,config,None,arr(0x3038))
 assert s and c and make(d,s,s,c),"EGL context"
 string=fn(G,"glGetString",C.c_char_p,U)
 renderer=string(0x1F01).decode();version=string(0x1F02).decode()
 assert "llvmpipe" in renderer.lower(),renderer
 create=fn(G,"glCreateShader",U,U);source=fn(G,"glShaderSource",None,U,I,C.POINTER(C.c_char_p),C.POINTER(I))
 compile_=fn(G,"glCompileShader",None,U);status=fn(G,"glGetShaderiv",None,U,U,C.POINTER(I))
 def shader(kind,code):
  sh=create(kind); text=C.c_char_p(code.encode());source(sh,1,C.byref(text),None);compile_(sh);ok=I();status(sh,0x8B81,C.byref(ok))
  assert ok.value,"shader compilation";return sh
 vs=shader(0x8B31,"#version 330\nvoid main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);gl_Position=vec4(p*2.0-1.0,0,1);}")
 fs=shader(0x8B30,"#version 330\nout vec4 color;void main(){color=vec4(0.2,0.4,0.6,1.0);}")
 program=fn(G,"glCreateProgram",U)(); attach=fn(G,"glAttachShader",None,U,U);attach(program,vs);attach(program,fs)
 fn(G,"glLinkProgram",None,U)(program);ok=I();fn(G,"glGetProgramiv",None,U,U,C.POINTER(I))(program,0x8B82,C.byref(ok));assert ok.value,"link"
 fn(G,"glUseProgram",None,U)(program)
 vao=U();fn(G,"glGenVertexArrays",None,I,C.POINTER(U))(1,C.byref(vao));fn(G,"glBindVertexArray",None,U)(vao)
 fn(G,"glViewport",None,I,I,I,I)(0,0,64,64)
 fn(G,"glClearColor",None,F,F,F,F)(0,0,0,1);fn(G,"glClear",None,U)(0x4000)
 fn(G,"glDrawArrays",None,U,I,I)(4,0,3);fn(G,"glFinish",None)()
 pixels=(C.c_ubyte*4)()
 fn(G,"glReadPixels",None,I,I,I,I,U,U,P)(32,32,1,1,0x1908,0x1401,pixels)
 assert fn(G,"glGetError",U)()==0,"GL error"
 assert all(abs(a-b)<=1 for a,b in zip(pixels,(51,102,153,255))),list(pixels)
 print(json.dumps({"renderer":renderer,"version":version,"egl":f"{major.value}.{minor.value}","pixel":list(pixels),"scope":"native CPU OpenGL draw/readback only"}))
finally:
 make(d,None,None,None)
 if c:destroyc(d,c)
 if s:destroys(d,s)
 terminate(d)
