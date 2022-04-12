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



	//fetch
	//const test = await fetch("http://artifact-sj1.synaptics.com:8081/artifactory/api/versions/PinormOS/Tarball?listFiles=1", {
	//  headers: {
//		"X-JFrog-Art-Api": "AKCp8krKugvEngM1hiiKeBbj9x1axt83ztvvx2AjkD8UtxEJNJSyaNWEu1wnc5dkxyq3qZh9o"
//	  }	
//})
//	console.log("@@@@@@@@@@@@@@@@@@@@@@@@@@@");
//	console.log(test);



	var url = "http://artifact-sj1.synaptics.com:8081/artifactory/api/versions/PinormOS/Tarball?listFiles=1";

	var xhr = new XMLHttpRequest();
	xhr.open("GET", url);

	xhr.setRequestHeader("X-JFrog-Art-Api", "AKCp8krKugvEngM1hiiKeBbj9x1axt83ztvvx2AjkD8UtxEJNJSyaNWEu1wnc5dkxyq3qZh9o");

	xhr.onreadystatechange = function () {
	   if (xhr.readyState === 4) {
		   	console.log("@@@@@@@@@@@@@@@@@@@@@@@@@@@!!!");
		  console.log(xhr.status);
		  console.log(xhr.responseText);
	   }};

	xhr.send();




    // GET request
    try {
      const data = await requestAPI<any>('general');
      console.log(data);
    } catch (reason) {
      console.error(`Error on GET /webds-api/general.\n${reason}`);
    }
	
	
	// PUT request
	const dataToSend = 
        [
			{
				name: "Test Set 1",
				id: "ee0d8223-d754-40cd-8d04-9b0900003d87",
				tests: ["FirmwareID", "AdcRangeTest", "TrxTrxShortTest", "FullRawCapTest", "NoiseTest", "SensorSpeedTest", "DevicePackageTest"]
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
			
	
		
	const eventHandler = (event: any) => {
        let obj = JSON.parse(event.data);
        console.log(obj)
		
		if (obj.status == 'finished')
		{
			console.log("SSSSSSSSSSSSSSSSSSSSSTOP")
			if (globalThis.source != undefined && globalThis.source.addEventListener != null) {
				globalThis.source.removeEventListener('production-tests', eventHandler, false);
				globalThis.source.close();
				console.log("close event source");
			}
			
		}
    }
	
	
	
	
	
	globalThis.source = new window.EventSource('/webds/production-tests');
	
	globalThis.source.onmessage = function(e) {
      console.log("!!!!!!!!!!!!!!!!!!Message");
    };
    globalThis.source.onopen = function(e) {
      // Reset reconnect frequency upon successful connection
       console.log("!!!!!!!!!!!!!!!!!!Open");
    };
    globalThis.source.onerror = function(e) {
      globalThis.source.close();
       console.log("!!!!!!!!!!!!!!!!!!Close");
    };
	
	
	console.log(globalThis.source);
	if (globalThis.source != null) {
		globalThis.source.addEventListener('production-tests', eventHandler, false);
	}
	else {
		console.log("event source is null");
	}
		
	
	// POST request
	const dataToSendPost = {
				test: "ee0d8223-d754-40cd-8d04-9b0900003d87"
			};
	const replyPost = await requestAPI<any>('production-tests/' + 'S3908-15.0.1', {
			body: JSON.stringify(dataToSendPost),
			method: 'POST',
		});
	console.log(replyPost);
	
	

	
	
	
	
	/*
	if (globalThis.source != undefined && globalThis.source.addEventListener != null) {
		globalThis.source.removeEventListener('production-tests', eventHandler, false);
		globalThis.source.close();
		console.log("close event source");
	}
	*/
	},
};

export default extension;

