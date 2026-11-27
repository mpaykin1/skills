#!/usr/bin/env python3
"""Instrument the pinned, already validated Lavapipe probe without changing rendering."""
from pathlib import Path
import sys
source=Path(sys.argv[1]).read_text()
def once(old,new):
 global source
 if source.count(old)!=1: raise ValueError("unexpected pinned source: "+old)
 source=source.replace(old,new,1)
once("int main(int argc,char**argv){",r'''
static int validation_errors=0, expected_errors=0, negative=0;
static VKAPI_ATTR VkBool32 VKAPI_CALL debug_callback(VkDebugUtilsMessageSeverityFlagBitsEXT severity,
 VkDebugUtilsMessageTypeFlagsEXT type,const VkDebugUtilsMessengerCallbackDataEXT* data,void* user){
 (void)type;(void)user;
 if(severity&VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT){
  validation_errors++;
  const char* id=data->pMessageIdName?data->pMessageIdName:"unknown";
  fprintf(stderr,"VVL_ERROR|%s|%s\n",id,data->pMessage?data->pMessage:"");
  if(negative && strcmp(id,"VUID-VkBufferCreateInfo-size-00912")==0){expected_errors++;return VK_TRUE;}
 }
 return VK_FALSE;
}
int main(int argc,char**argv){''')
once("CHECK(argc==3);","CHECK(argc==3||argc==4);negative=argc==4;")
once("VkInstanceCreateInfo ii={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&app};VkInstance instance;VK(vkCreateInstance(&ii,NULL,&instance));",r'''
 const char* layer="VK_LAYER_KHRONOS_validation";
 const char* extensions[]={VK_EXT_DEBUG_UTILS_EXTENSION_NAME,VK_EXT_VALIDATION_FEATURES_EXTENSION_NAME};
 VkDebugUtilsMessengerCreateInfoEXT debug={.sType=VK_STRUCTURE_TYPE_DEBUG_UTILS_MESSENGER_CREATE_INFO_EXT,
  .messageSeverity=VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT,
  .messageType=VK_DEBUG_UTILS_MESSAGE_TYPE_GENERAL_BIT_EXT|VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT|VK_DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT,
  .pfnUserCallback=debug_callback};
 VkValidationFeatureEnableEXT sync=VK_VALIDATION_FEATURE_ENABLE_SYNCHRONIZATION_VALIDATION_EXT;
 VkValidationFeaturesEXT features={.sType=VK_STRUCTURE_TYPE_VALIDATION_FEATURES_EXT,.pNext=&debug,.enabledValidationFeatureCount=1,.pEnabledValidationFeatures=&sync};
 VkInstanceCreateInfo ii={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pNext=&features,.pApplicationInfo=&app,
  .enabledLayerCount=1,.ppEnabledLayerNames=&layer,.enabledExtensionCount=2,.ppEnabledExtensionNames=extensions};
 VkInstance instance;VK(vkCreateInstance(&ii,NULL,&instance));
 PFN_vkCreateDebugUtilsMessengerEXT create_debug=(PFN_vkCreateDebugUtilsMessengerEXT)vkGetInstanceProcAddr(instance,"vkCreateDebugUtilsMessengerEXT");
 PFN_vkDestroyDebugUtilsMessengerEXT destroy_debug=(PFN_vkDestroyDebugUtilsMessengerEXT)vkGetInstanceProcAddr(instance,"vkDestroyDebugUtilsMessengerEXT");
 CHECK(create_debug&&destroy_debug);VkDebugUtilsMessengerEXT messenger;VK(create_debug(instance,&debug,NULL,&messenger));
''')
once("vkGetDeviceQueue(d,family,0,&queue);",r'''vkGetDeviceQueue(d,family,0,&queue);
 if(negative){
  VkBufferCreateInfo bad={.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=0,.usage=VK_BUFFER_USAGE_TRANSFER_DST_BIT,.sharingMode=VK_SHARING_MODE_EXCLUSIVE};
  VkBuffer ignored=VK_NULL_HANDLE;VkResult result=vkCreateBuffer(d,&bad,NULL,&ignored);
  CHECK(result==VK_ERROR_VALIDATION_FAILED_EXT);CHECK(expected_errors==1&&validation_errors==1);
  vkDestroyDevice(d,NULL);destroy_debug(instance,messenger,NULL);vkDestroyInstance(instance,NULL);
  CHECK(validation_errors==1);puts("VVL deliberate invalid buffer intercepted");return 0;
 }
''')
once("vkDestroyDevice(d,NULL);vkDestroyInstance(instance,NULL);return 0;","vkDestroyDevice(d,NULL);destroy_debug(instance,messenger,NULL);vkDestroyInstance(instance,NULL);CHECK(validation_errors==0);puts(\"VVL core+sync: zero errors\");return 0;")
Path(sys.argv[2]).write_text(source)
