// Uses the official CLI's installed SDK and encoder; no scene transforms.
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const requireCLI=createRequire(process.argv[1]);
const {EXTMeshoptCompression}=await import(pathToFileURL(requireCLI.resolve('@gltf-transform/extensions')).href);
export default {
  onProgramReady: async ({program,io}) => {
    program.command('meshopt-lossless', 'Lossless Meshopt encoding preserving node hierarchy')
      .argument('<input>', 'Input GLB')
      .argument('<output>', 'Output GLB')
      .action(async ({args}) => {
        const document=await io.read(args.input);
        document.createExtension(EXTMeshoptCompression).setRequired(true)
          .setEncoderOptions({method:EXTMeshoptCompression.EncoderMethod.QUANTIZE});
        await io.write(args.output,document);
      });
  }
};
