/* CPU bridge to the unmodified upstream MikkTSpace C library. */
#include <limits.h>
#include <stddef.h>
#include <string.h>
#include "mikktspace.h"
typedef struct { int faces; const float *p,*n,*uv; float *t; } Mesh;
static Mesh *mesh(const SMikkTSpaceContext *c) {return (Mesh*)c->m_pUserData;}
static int faces(const SMikkTSpaceContext *c) {return mesh(c)->faces;}
static int corners(const SMikkTSpaceContext *c, int f) {(void)c;(void)f;return 3;}
static void pos(const SMikkTSpaceContext *c,float out[],int f,int v){memcpy(out,mesh(c)->p+((size_t)f*3+v)*3,3*sizeof(float));}
static void norm(const SMikkTSpaceContext *c,float out[],int f,int v){memcpy(out,mesh(c)->n+((size_t)f*3+v)*3,3*sizeof(float));}
static void tex(const SMikkTSpaceContext *c,float out[],int f,int v){memcpy(out,mesh(c)->uv+((size_t)f*3+v)*2,2*sizeof(float));}
static void tangent(const SMikkTSpaceContext *c,const float t[],float sign,int f,int v){float *o=mesh(c)->t+((size_t)f*3+v)*4;memcpy(o,t,3*sizeof(float));o[3]=sign;}
int cover_mikk(int count,const float *p,const float *n,const float *uv,float *t){
    if(count<1 || count>INT_MAX/12 || !p || !n || !uv || !t)return 0;
    Mesh m={count,p,n,uv,t};SMikkTSpaceInterface i={0};
    i.m_getNumFaces=faces;i.m_getNumVerticesOfFace=corners;i.m_getPosition=pos;i.m_getNormal=norm;i.m_getTexCoord=tex;i.m_setTSpaceBasic=tangent;
    SMikkTSpaceContext c={&i,&m};return genTangSpaceDefault(&c)?1:0;
}
