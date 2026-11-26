#!/usr/bin/env python3
"""PathFinding.js A* browser navigation from authored LDtk/Tiled/Godot geometry.

Only converts *verified* full-cel scene navigation metadata into a per-actor
walkability grid; neither fabricates poses nor changes approved sprites.
"""
from __future__ import annotations
from collections import deque
import math

class PathFindingBridgeError(ValueError):pass

def fail(msg):raise PathFindingBridgeError('PathFinding.js source geometry blocked: '+str(msg))
def finite(v):return type(v) in (int,float) and math.isfinite(v)

def inside(x,y,polygon):
    # Ray-casting polygon. Boundaries are not guaranteed traversable.
    odd=False
    for i in range(len(polygon)):
        ax,ay=polygon[i];bx,by=polygon[(i+1)%len(polygon)]
        if (ay>y)!=(by>y) and x<(bx-ax)*(y-ay)/(by-ay)+ax:odd=not odd
    return odd

def prepare(scene, actors, width, height):
    """Return real authored walkable grids only for explicitly navigated actors."""
    gd=scene.get('godot',{})
    if not isinstance(gd,dict):fail('scene.godot must be object')
    movers=gd.get('navigation_actors',{})
    if not movers:return None
    if not isinstance(movers,dict):fail('navigation_actors must be object')
    polygons=gd.get('walkable_polygons',[])
    obstacles=gd.get('obstacles',[])
    if not isinstance(polygons,list) or not polygons:fail('Authored walkable polygons required')
    if not isinstance(obstacles,list):fail('Authored obstacle rectangles must be list')
    for poly in polygons:
        if not isinstance(poly,list) or not 3<=len(poly)<=128 or any(not isinstance(p,list) or len(p)!=2 or not all(finite(n) for n in p) for p in poly):fail('Invalid navigation polygon')
    for rect in obstacles:
        if not isinstance(rect,list) or len(rect)!=4 or not all(finite(n) for n in rect) or rect[2]<=0 or rect[3]<=0:fail('Invalid obstacle')
    browser=scene.get('browser_navigation',{})
    if not isinstance(browser,dict):fail('browser_navigation must be object')
    cell=browser.get('cell_px',8)
    if type(cell) is not int or not 4<=cell<=64:fail('cell_px must be integer 4..64 source pixels')
    gw=math.ceil(width/cell);gh=math.ceil(height/cell)
    if gw*gh>100000:fail('Browser navigation grid exceeds 100000 cells; increase cell_px')
    centers=[[(min(width-.5,(x+.5)*cell), min(height-.5,(y+.5)*cell)) for x in range(gw)] for y in range(gh)]
    base=[[0 if any(inside(cx,cy,p) for p in polygons) and not any(l<=cx<l+w and t<=cy<t+h for l,t,w,h in obstacles) else 1
           for cx,cy in row] for row in centers]
    result={};roster={a['id']:a for a in actors}
    def cellof(pt):
        if not isinstance(pt,list) or len(pt)!=2 or not all(finite(x) for x in pt):fail('Waypoint must be finite [x,y]')
        x,y=pt
        if not 0<=x<width or not 0<=y<height:fail('Waypoint outside source illustration')
        return min(gw-1,int(x//cell)),min(gh-1,int(y//cell))
    def reachable(matrix,p,q):
        if matrix[p[1]][p[0]] or matrix[q[1]][q[0]]:return False
        if p==q:return True
        queue=deque([p]);seen={p}
        while queue:
            x,y=queue.popleft()
            for u,v in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if 0<=u<gw and 0<=v<gh and not matrix[v][u] and (u,v) not in seen:
                    if (u,v)==q:return True
                    seen.add((u,v));queue.append((u,v))
        return False
    for aid, opts in movers.items():
        if aid not in roster:fail('Map refers to unknown actor '+str(aid))
        actor=roster[aid]
        if not isinstance(opts,dict):fail('Navigation actor settings invalid')
        actions=actor.get('actions',[])
        loc=actor.get('locomotion')
        if not loc or loc.get('mode') not in ('walk','run','stairs_up','stairs_down') or loc['mode'] not in actions:
            fail('Navigation actor has no certified original walking/running full-cel poses: '+aid)
        if not any(a not in ('walk','run','stairs_up','stairs_down') for a in actions):
            fail('Navigation actor needs an independently painted non-walking action: '+aid)
        b=actor['box'];x,y,w,h=b
        # Author's waypoint targets are source-relative root positions, like Godot.
        # Inflate obstacles by the actual authored foot-contact footprint radius.
        clearance=max(2.0,min(w,h)*.14)
        matrix=[]
        for yy,row in enumerate(centers):
            arr=[]
            for xx,(cx,cy) in enumerate(row):
                if base[yy][xx]:arr.append(1);continue
                if any(l-clearance<=cx<l+ww+clearance and t-clearance<=cy<t+hh+clearance for l,t,ww,hh in obstacles):
                    arr.append(1);continue
                arr.append(0)
            matrix.append(arr)
        waypoints=opts.get('waypoints',[])
        if not isinstance(waypoints,list) or not 2<=len(waypoints)<=64:fail('Need 2..64 authored waypoints')
        speed=opts.get('speed_px_s',24)
        if not finite(speed) or not 2<=speed<=500:fail('Invalid actor navigation speed')
        p=cellof([x,y]); sequence=[p]+[cellof(point) for point in waypoints]
        for q in sequence[1:]:
            if not reachable(matrix,p,q):fail(f'Unreachable path / blocked route for {aid}: {p} -> {q}')
            p=q
        result[aid]={'width':gw,'height':gh,'cell_px':cell,'matrix':matrix,
                     'waypoints':waypoints,'speed_px_s':float(speed),
                     'moving_action':loc['mode']}
    return {'engine':'PathFinding.js','version':'0.4.18','algorithm':'AStarFinder','diagonal':False,
            'actors':result,'authored_geometry':True}
