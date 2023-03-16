import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin,
} from '@jupyterlab/application';

import { ICommandPalette } from '@jupyterlab/apputils';

import { ILauncher } from '@jupyterlab/launcher';

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
	},
};

export default extension;

