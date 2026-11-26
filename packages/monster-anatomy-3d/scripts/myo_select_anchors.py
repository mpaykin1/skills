"""Select a Z-Anatomy bridge muscle pair in the *installed* MyoGenerator UI.

Run inside Blender Text Editor: change TARGET below or call select_pair('name_L').
This only sets objects/names; it does not call unverified creation operators.
"""
import bpy

def select_pair(tag):
    scene=bpy.context.scene
    origin=bpy.data.objects.get('ZA_ORIGIN_'+tag)
    insertion=bpy.data.objects.get('ZA_INSERTION_'+tag)
    if not origin or not insertion:
        raise ValueError('No Z-Anatomy anchor pair: '+tag)
    required=('origin_object','insertion_object','muscle_Name')
    missing=[k for k in required if not hasattr(scene,k)]
    if missing:
        raise RuntimeError('Enable MyoGeneratorRemix first; missing Blender scene properties: '+', '.join(missing))
    scene.origin_object=origin
    scene.insertion_object=insertion
    scene.muscle_Name=tag
    for obj in bpy.context.selected_objects: obj.select_set(False)
    origin.select_set(True)
    bpy.context.view_layer.objects.active=origin
    print('MyoGenerator origin/insertion selected:',tag,
          origin.name,'->',insertion.name)
    return origin,insertion

if __name__=='__main__':
    TARGET='trapezius_L'
    select_pair(TARGET)
