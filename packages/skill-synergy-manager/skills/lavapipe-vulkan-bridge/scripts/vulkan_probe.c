#include <vulkan/vulkan.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#define VK(x) do { VkResult r=(x); if(r!=VK_SUCCESS){fprintf(stderr,"%s: %d\n",#x,r);exit(1);} }while(0)
#define CHECK(x) do {if(!(x)){fprintf(stderr,"failed: %s\n",#x);exit(1);}}while(0)
#define W 64
#define H 64
static uint32_t memtype(VkPhysicalDevice p,uint32_t bits,VkMemoryPropertyFlags flags){
 VkPhysicalDeviceMemoryProperties m;vkGetPhysicalDeviceMemoryProperties(p,&m);
 for(uint32_t i=0;i<m.memoryTypeCount;i++)if((bits&(1u<<i))&&(m.memoryTypes[i].propertyFlags&flags)==flags)return i;
 fprintf(stderr,"no matching memory type\n");exit(1);
}
static VkDeviceMemory alloc(VkDevice d,VkPhysicalDevice p,VkMemoryRequirements req,VkMemoryPropertyFlags flags){
 VkMemoryAllocateInfo i={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=req.size,.memoryTypeIndex=memtype(p,req.memoryTypeBits,flags)};
 VkDeviceMemory m;VK(vkAllocateMemory(d,&i,NULL,&m));return m;
}
static VkShaderModule shader(VkDevice d,const char* file){
 FILE*f=fopen(file,"rb");CHECK(f);CHECK(fseek(f,0,SEEK_END)==0);long n=ftell(f);CHECK(n>0&&n%4==0);rewind(f);
 uint32_t*code=malloc(n);CHECK(code&&fread(code,1,n,f)==(size_t)n);fclose(f);
 VkShaderModuleCreateInfo i={.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,.codeSize=(size_t)n,.pCode=code};
 VkShaderModule s;VK(vkCreateShaderModule(d,&i,NULL,&s));free(code);return s;
}
int main(int argc,char**argv){
 CHECK(argc==3);
 VkApplicationInfo app={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.pApplicationName="Nexus CPU Vulkan",.apiVersion=VK_API_VERSION_1_1};
 VkInstanceCreateInfo ii={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&app};VkInstance instance;VK(vkCreateInstance(&ii,NULL,&instance));
 uint32_t n=0;VK(vkEnumeratePhysicalDevices(instance,&n,NULL));CHECK(n==1);VkPhysicalDevice p;VK(vkEnumeratePhysicalDevices(instance,&n,&p));
 VkPhysicalDeviceProperties prop;vkGetPhysicalDeviceProperties(p,&prop);CHECK(prop.deviceType==VK_PHYSICAL_DEVICE_TYPE_CPU);CHECK(strstr(prop.deviceName,"llvmpipe")||strstr(prop.deviceName,"lavapipe"));
 vkGetPhysicalDeviceQueueFamilyProperties(p,&n,NULL);VkQueueFamilyProperties*q=calloc(n,sizeof(*q));CHECK(q);vkGetPhysicalDeviceQueueFamilyProperties(p,&n,q);uint32_t family=0;while(family<n&&!(q[family].queueFlags&VK_QUEUE_GRAPHICS_BIT))family++;CHECK(family<n);free(q);
 float priority=1;VkDeviceQueueCreateInfo qi={.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,.queueFamilyIndex=family,.queueCount=1,.pQueuePriorities=&priority};
 VkDeviceCreateInfo di={.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,.queueCreateInfoCount=1,.pQueueCreateInfos=&qi};VkDevice d;VK(vkCreateDevice(p,&di,NULL,&d));VkQueue queue;vkGetDeviceQueue(d,family,0,&queue);
 VkImageCreateInfo im={.sType=VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,.imageType=VK_IMAGE_TYPE_2D,.format=VK_FORMAT_R8G8B8A8_UNORM,.extent={W,H,1},.mipLevels=1,.arrayLayers=1,.samples=VK_SAMPLE_COUNT_1_BIT,.tiling=VK_IMAGE_TILING_OPTIMAL,.usage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT,.sharingMode=VK_SHARING_MODE_EXCLUSIVE,.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED};
 VkImage image;VK(vkCreateImage(d,&im,NULL,&image));VkMemoryRequirements req;vkGetImageMemoryRequirements(d,image,&req);VkDeviceMemory imageMem=alloc(d,p,req,VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);VK(vkBindImageMemory(d,image,imageMem,0));
 VkImageViewCreateInfo vi={.sType=VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,.image=image,.viewType=VK_IMAGE_VIEW_TYPE_2D,.format=im.format,.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1}};VkImageView view;VK(vkCreateImageView(d,&vi,NULL,&view));
 VkBufferCreateInfo bi={.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=W*H*4,.usage=VK_BUFFER_USAGE_TRANSFER_DST_BIT,.sharingMode=VK_SHARING_MODE_EXCLUSIVE};VkBuffer buf;VK(vkCreateBuffer(d,&bi,NULL,&buf));vkGetBufferMemoryRequirements(d,buf,&req);VkDeviceMemory bufMem=alloc(d,p,req,VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);VK(vkBindBufferMemory(d,buf,bufMem,0));
 VkAttachmentDescription ad={.format=im.format,.samples=VK_SAMPLE_COUNT_1_BIT,.loadOp=VK_ATTACHMENT_LOAD_OP_CLEAR,.storeOp=VK_ATTACHMENT_STORE_OP_STORE,.stencilLoadOp=VK_ATTACHMENT_LOAD_OP_DONT_CARE,.stencilStoreOp=VK_ATTACHMENT_STORE_OP_DONT_CARE,.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED,.finalLayout=VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL};
 VkAttachmentReference ar={0,VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};
 VkSubpassDescription sub={.pipelineBindPoint=VK_PIPELINE_BIND_POINT_GRAPHICS,.colorAttachmentCount=1,.pColorAttachments=&ar};
 VkSubpassDependency deps[2]={{.srcSubpass=VK_SUBPASS_EXTERNAL,.dstSubpass=0,.srcStageMask=VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,.dstStageMask=VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,.dstAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT},{.srcSubpass=0,.dstSubpass=VK_SUBPASS_EXTERNAL,.srcStageMask=VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,.dstStageMask=VK_PIPELINE_STAGE_TRANSFER_BIT,.srcAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT,.dstAccessMask=VK_ACCESS_TRANSFER_READ_BIT}};
 VkRenderPassCreateInfo ri={.sType=VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO,.attachmentCount=1,.pAttachments=&ad,.subpassCount=1,.pSubpasses=&sub,.dependencyCount=2,.pDependencies=deps};VkRenderPass rp;VK(vkCreateRenderPass(d,&ri,NULL,&rp));
 VkFramebufferCreateInfo fi={.sType=VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO,.renderPass=rp,.attachmentCount=1,.pAttachments=&view,.width=W,.height=H,.layers=1};VkFramebuffer fb;VK(vkCreateFramebuffer(d,&fi,NULL,&fb));
 VkShaderModule vs=shader(d,argv[1]),fs=shader(d,argv[2]);VkPipelineShaderStageCreateInfo stages[2]={{.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_VERTEX_BIT,.module=vs,.pName="main"},{.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_FRAGMENT_BIT,.module=fs,.pName="main"}};
 VkPipelineVertexInputStateCreateInfo vert={.sType=VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO};
 VkPipelineInputAssemblyStateCreateInfo ia={.sType=VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,.topology=VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST};
 VkViewport viewport={0,0,W,H,0,1};VkRect2D rect={{0,0},{W,H}};VkPipelineViewportStateCreateInfo vp={.sType=VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,.viewportCount=1,.pViewports=&viewport,.scissorCount=1,.pScissors=&rect};
 VkPipelineRasterizationStateCreateInfo raster={.sType=VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO,.polygonMode=VK_POLYGON_MODE_FILL,.cullMode=VK_CULL_MODE_NONE,.frontFace=VK_FRONT_FACE_COUNTER_CLOCKWISE,.lineWidth=1};
 VkPipelineMultisampleStateCreateInfo ms={.sType=VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,.rasterizationSamples=VK_SAMPLE_COUNT_1_BIT};
 VkPipelineColorBlendAttachmentState ba={.colorWriteMask=15};VkPipelineColorBlendStateCreateInfo blend={.sType=VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO,.attachmentCount=1,.pAttachments=&ba};
 VkPipelineLayoutCreateInfo li={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};VkPipelineLayout layout;VK(vkCreatePipelineLayout(d,&li,NULL,&layout));
 VkGraphicsPipelineCreateInfo gi={.sType=VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,.stageCount=2,.pStages=stages,.pVertexInputState=&vert,.pInputAssemblyState=&ia,.pViewportState=&vp,.pRasterizationState=&raster,.pMultisampleState=&ms,.pColorBlendState=&blend,.layout=layout,.renderPass=rp};VkPipeline pipe;VK(vkCreateGraphicsPipelines(d,VK_NULL_HANDLE,1,&gi,NULL,&pipe));
 VkCommandPoolCreateInfo pi={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,.queueFamilyIndex=family};VkCommandPool pool;VK(vkCreateCommandPool(d,&pi,NULL,&pool));
 VkCommandBufferAllocateInfo ai={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=pool,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};VkCommandBuffer cmd;VK(vkAllocateCommandBuffers(d,&ai,&cmd));
 VkCommandBufferBeginInfo begin={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT};VK(vkBeginCommandBuffer(cmd,&begin));
 VkClearValue clear={.color={{0,0,0,1}}};VkRenderPassBeginInfo rb={.sType=VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO,.renderPass=rp,.framebuffer=fb,.renderArea=rect,.clearValueCount=1,.pClearValues=&clear};
 vkCmdBeginRenderPass(cmd,&rb,VK_SUBPASS_CONTENTS_INLINE);vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_GRAPHICS,pipe);vkCmdDraw(cmd,3,1,0,0);vkCmdEndRenderPass(cmd);
 VkBufferImageCopy copy={.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1},.imageExtent={W,H,1}};vkCmdCopyImageToBuffer(cmd,image,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,buf,1,&copy);
 VkBufferMemoryBarrier barrier={.sType=VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER,.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT,.dstAccessMask=VK_ACCESS_HOST_READ_BIT,.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.buffer=buf,.offset=0,.size=VK_WHOLE_SIZE};vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,0,NULL,1,&barrier,0,NULL);
 VK(vkEndCommandBuffer(cmd));VkSubmitInfo submit={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&cmd};VK(vkQueueSubmit(queue,1,&submit,VK_NULL_HANDLE));VK(vkQueueWaitIdle(queue));
 void* data;VK(vkMapMemory(d,bufMem,0,VK_WHOLE_SIZE,0,&data));uint8_t* pixel=data;uint8_t* center=pixel+4*(W*(H/2)+W/2);int expected[4]={51,102,153,255};for(int i=0;i<4;i++)CHECK(abs((int)center[i]-expected[i])<=1);CHECK(pixel[0]==0&&pixel[1]==0&&pixel[2]==0&&pixel[3]==255);
 printf("CPU Vulkan %s; center RGBA %u,%u,%u,%u; background %u,%u,%u,%u\n",prop.deviceName,center[0],center[1],center[2],center[3],pixel[0],pixel[1],pixel[2],pixel[3]);vkUnmapMemory(d,bufMem);
 vkDestroyCommandPool(d,pool,NULL);vkDestroyPipeline(d,pipe,NULL);vkDestroyPipelineLayout(d,layout,NULL);vkDestroyShaderModule(d,fs,NULL);vkDestroyShaderModule(d,vs,NULL);vkDestroyFramebuffer(d,fb,NULL);vkDestroyRenderPass(d,rp,NULL);vkDestroyBuffer(d,buf,NULL);vkFreeMemory(d,bufMem,NULL);vkDestroyImageView(d,view,NULL);vkDestroyImage(d,image,NULL);vkFreeMemory(d,imageMem,NULL);vkDestroyDevice(d,NULL);vkDestroyInstance(instance,NULL);return 0;
}
