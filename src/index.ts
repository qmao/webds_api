import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin,
} from '@jupyterlab/application';

import { ICommandPalette } from '@jupyterlab/apputils';

import { ILauncher } from '@jupyterlab/launcher';

import { requestAPI } from './handler';

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
	
	
	// POST request
	const dataToSend = 
        [
			{
				name: "Test Set 1",
				id: "ee0d8223-d754-40cd-8d04-9b0900003d87",
				tests: ["NoiseTest", "FirmwareID", "LockdownTest", "Configuration"]
			},
			{
				name: "Test Set 2",
				id: "b7f7ec88-f551-4593-9087-7a230be5a483",
				tests: []
			}
		];

	const reply = await requestAPI<any>('production-tests/' + 'S3908-15.0.1', {
				body: JSON.stringify(dataToSend),
				method: 'PUT',
			});
            console.log(reply);
			
	// POST request
	const dataToSendPost = {
				test: "ee0d8223-d754-40cd-8d04-9b0900003d87"
			};
	const replyPost = await requestAPI<any>('production-tests/' + 'S3908-15.0.1', {
			body: JSON.stringify(dataToSendPost),
			method: 'POST',
		});
	console.log(replyPost);
	
	},
};

export default extension;

