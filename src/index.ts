import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin,
} from '@jupyterlab/application';

import { ICommandPalette } from '@jupyterlab/apputils';

import { ILauncher } from '@jupyterlab/launcher';

import { requestAPI } from './handler';

declare global {
    var source: EventSource;
}

/**
 * Initialization data for the server-extension extension.
 */
const extension: JupyterFrontEndPlugin<void> = {
  id: 'server-extension',
  autoStart: true,
  optional: [ILauncher],
  requires: [ICommandPalette],
  activate: async (
    app: JupyterFrontEnd,
    palette: ICommandPalette,
    launcher: ILauncher | null
  ) => {
    console.log('JupyterLab extension server-extension is activated!');


    // GET request
    try {
      const data = await requestAPI<any>('general');
      console.log(data);
    } catch (reason) {
      console.error(`Error on GET /webds-api/general.\n${reason}`);
    }
	
	

	},
};

export default extension;

