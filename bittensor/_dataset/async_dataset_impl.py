##################
##### Import #####
##################
import torch
import concurrent.futures
import time
import psutil
import random
import argparse
from tqdm import tqdm
import bittensor
import streamlit as st
import numpy as np
import asyncio
import aiohttp
import json
import os
from fsspec.asyn import AsyncFileSystem, sync, sync_wrapper


class Dataset:
    """ Implementation for the dataset class, which handles dataloading from ipfs
    """
    def __init__(self, loop=None, batch_size=10, datasets=None):
        
        # Used to retrieve directory contentx
        self.ipfs_url = 'http://global.ipfs.opentensor.ai/api/v0'
        self.dataset_dir = 'http://global.ipfs.opentensor.ai/api/v0/cat' 
        self.text_dir = 'http://global.ipfs.opentensor.ai/api/v0/object/get'
        self.mountain_hash = 'QmSdDg6V9dgpdAFtActs75Qfc36qJtm9y8a7yrQ1rHm7ZX'
        # Used when current corpus has been exhausted
        self.refresh_corpus = False
        self.set_datasets(datasets=datasets)


    def set_event_loop(self, loop=None):
        if loop == None:
            loop = asyncio.get_event_loop()
        self.loop = loop
        return self.loop

    self.loop 
    @property
    def loop(self):
        return getattr(self, '_loop',asyncio.get_event_loop())

    self.loop = loop 
    @loop.setter
    def loop(self, loop):
        if loop == None:
            loop = asyncio.get_event_loop()
        self._loop = loop
        return loop

    def async_run(self, job):
        return self.loop.run_until_complete(job)



    async def async_get_dataset_hashes(self):
        mountain_meta = {'Name': 'mountain', 'Folder': 'meta_data', 'Hash': self.mountain_hash}
        response = await self.ipfs_get_object(mountain_meta)
        response = response.get('Links', None)
        return response



    @property
    def dataset2size(self):
        return {k:v['Size'] for k,v in self.dataset2hash.items()}


    @property
    def available_datasets(self):
        return list(self.dataset2hash.keys())

    @property
    def datasets(self):
        if not hasattr(self, 'selected_datasets'):
            self.set_datasets(datasets=self.available_datasets)
        return self.selected_datasets 

    def set_datasets(self, datasets=None):
        if datasets == None:
            datasets = self.available_datasets
        for d in datasets:
            assert d in  self.available_datasets, f'{d} does not exist, please select {self.available_datasets}'
            self.selected_datasets.append(d)

        return self.selected_datasets
        

    @property
    def dataset2hash(self):
        if not hasattr(self, 'dataset_table'):
            self.dataset_hashes = self.get_dataset_hashes()
        return {v['Name'].replace('.txt', '') :v for v in self.dataset_hashes}
    
    def get_dataset_hashes(self):
        hash_list =  asyncio.run(self.async_get_dataset_hashes())
        return hash_list

    async def get_text(self, file_meta):
        links = await self.get_links(file_meta)
        st.write(links)
        for link in links:
            res = await self.ipfs_post('object/get', params={'arg':link['Hash']})
            total_data = b''
            async for data in res.content.iter_chunked(1024):  
                total_data += data
                st.write(data)
                hashes = data.decode().split('}, {')
                decoded_hashes = []
                for i in range(len(hashes)-1):
                    try:
                        decoded_hashes += [json.loads(json.loads('"{' + hashes[i+1] +  '}"'))]
                    except json.JSONDecodeError:
                        pass
                    # hashes[i] =bytes('{'+ hashes[i+1] + '}')
                st.write(decoded_hashes)
                st.write(b'{"Links":[],' == data[:len(b'{"Links":[],')])
                break


        
    async def get_links(self, file_meta, resursive=False, **kwargs):
        response = await self.ipfs_get_object(file_meta)
        response_links = response.get('Links', [])
        if resursive:
            link_map = {}
            job2hash_map = {}
            job_list = []
            st.write(response_links)
            if resursive :
                for response_link in response_links:
                    # st.write('response_link', response_link)
                    st.write(await self.ipfs_cat(response_link))
                    # inner_links = await self.get_links(response_link, resursive=False)
                    # st.write(len(inner_links))
                    # job_list.append(job)

            # for response_link, x in zip(response_links, await asyncio.gather(*job_list)):
            
            # cnt = 0
            # for fut in asyncio.as_completed(job_list):
            #     cnt += 1
            #     st.write(cnt)

            #     st.write(len(link_map))
            #     link_map[response_link['Hash']] = await fut
            
            return link_map
            
        return response_links

    async def get_file_metas(self, file_meta):
        response = await self.ipfs_get_object(file_meta)
        return response
    async def get_files(self, file_meta, limit=1000, **kwargs):

        file_meta_list = kwargs.get('file_meta_list', [])
        recursion = kwargs.get('recursion', 1)
        if len(file_meta_list)>=limit:
            return file_meta_list
        response_dict =  await self.ipfs_get_object(file_meta)
        response_links =  response_dict.get('Links')
        response_data = response_dict.get('Data', []) 
        folder_get_file_jobs = []
        st.write(recursion,len(response_links), 'data',len(response_data), type(response_data))
        if len(response_links)>0:
            job_list = []
            for response_link in response_links:
                
                job =  self.get_files(file_meta=response_link, file_meta_list=file_meta_list, recursion= recursion+1)
                job_list.append(job)
            await asyncio.gather(*job_list)
        elif len(response_links) == 0:
            st.write(len(json.loads(response_data)))

            file_meta_list  += response_data
    
        return file_meta_list
        # folder_get_file_jobs = []
        # for link_file_meta in response_links:
        #     job = await self.get_files(file_meta=link_file_meta, file_meta_list=file_meta_list)
        #     folder_get_file_jobs.append(job)

        # if folder_get_file_jobs:
        #     return await asyncio.gather(*folder_get_file_jobs)

        
    
    async def ipfs_cat(self, file_meta, timeout=10, action='post'):
        address = self.ipfs_url + '/cat'
        if action == 'get':
            response = await asyncio.wait_for(self.api_get( url=address,  params={'arg': file_meta['Hash']}), timeout=timeout)
        elif action == 'post':
            response = await asyncio.wait_for(self.api_post( url=address, params={'arg': file_meta['Hash']}), timeout=timeout)
        # except Exception as E:
        #     logger.error(f"Failed to get from IPFS {file_meta['Name']} {E}")
        #     return None
        return await response.json()

    async def ipfs_object_get(self, file_meta, timeout=2):
        response = await asyncio.wait_for(self.api_post( url=self.ipfs_url+'/object/get',  params={'arg': file_meta['Hash']}), timeout=timeout)
        return await response.json()


    async def ipfs_get_object(self, file_meta, timeout=10, action='post'):
        address = self.ipfs_url + '/object/get'
        if action == 'get':
            response = await asyncio.wait_for(self.api_get( url=address,  params={'arg': file_meta['Hash']}), timeout=timeout)
        elif action == 'post':
            response = await asyncio.wait_for(self.api_post( url=address, params={'arg': file_meta['Hash']}), timeout=timeout)
        # except Exception as E:
        #     logger.error(f"Failed to get from IPFS {file_meta['Name']} {E}")
        #     return None
        return await response.json()

    async def get_ipfs_directory(self, address: str, file_meta: dict, action: str = 'post', timeout : int = 2):
        r"""Connects to IPFS gateway and retrieves directory.
        Args:
            address: (:type:`str`, required):
                The target address of the request. 
            params: (:type:`tuple`, optional):
                The arguments of the request. eg. (('arg', dataset_hash),)
            action: (:type:`str`, optional):
                POST or GET.
            timeout: (:type:`int`, optional):
                Timeout for getting the server's response. 
        Returns:
            dict: A dictionary of the files inside of the genesis_datasets and their hashes.
        """
        # session = requests.Session()
        # session.params.update((('arg', file_meta['Hash']), ))
        # try:
        if action == 'get':
            response = await asyncio.wait_for(self.api_get( url=address,  params={'arg': file_meta['Hash']}), timeout=timeout)
        elif action == 'post':
            response = await asyncio.wait_for(self.api_post( url=address, params={'arg': file_meta['Hash']}), timeout=timeout)
        # except Exception as E:
        #     logger.error(f"Failed to get from IPFS {file_meta['Name']} {E}")
        #     return None


        return await response.json()

    @staticmethod
    async def get_client_session(*args,**kwargs):
        # timeout = aiohttp.ClientTimeout(sock_connect=1, sock_read=5)
        # kwargs = {"timeout": timeout, **kwargs}
        return aiohttp.ClientSession(**kwargs)

    async def api_get(self, url, session=None, **kwargs):
        if session == None:
            session = await self.get_client_session()
        headers = kwargs.pop('headers', {}) 
        params = kwargs.pop('params', kwargs)
        res = await session.get(url, params=params,headers=headers)
        await session.close()
        return res

    async def async_ipfs_post(endpoint, **kwargs):
        res = self.api_post(url=os.path.join(self.ipfs_url, endpoint),**kwargs )

    

    async def ipfs_post(self,endpoint, return_json=False, iter_chunk=1024, **kwargs):
        res = await self.api_post(url=os.path.join(self.ipfs_url, endpoint),**kwargs )

        if return_json:
            res = await res.json()
        st.write(res)

        return res

    async def api_post(self, url, return_json = False, **kwargs):
        
        async with (await self.get_client_session()) as session:


            headers = kwargs.pop('headers', {}) 
            params = kwargs.pop('params', kwargs)
            res = await session.post(url, params=params,headers=headers)

            if return_json: 
                res = await res.json()
        return res

    async def api_get(self, url, session=None, **kwargs):
        if session == None:
            session = await self.get_client_session()
        headers = kwargs.pop('headers', {}) 
        params = kwargs.pop('params', kwargs)
        res = await session.get(url, params=params,headers=headers)
        await session.close()
        return res



if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    dataset = Dataset()   