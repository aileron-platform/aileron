import React, { createContext, useContext } from 'react';

interface AgentSettingsAuthorizationValue {
  readOnly: boolean;
}

const AgentSettingsAuthorizationContext =
  createContext<AgentSettingsAuthorizationValue>({ readOnly: false });

interface AgentSettingsAuthorizationProviderProps {
  readOnly: boolean;
  children: React.ReactNode;
}

export const AgentSettingsAuthorizationProvider: React.FC<
  AgentSettingsAuthorizationProviderProps
> = ({ readOnly, children }) => (
  <AgentSettingsAuthorizationContext.Provider value={{ readOnly }}>
    {children}
  </AgentSettingsAuthorizationContext.Provider>
);

export const useAgentSettingsAuthorization = (): AgentSettingsAuthorizationValue => (
  useContext(AgentSettingsAuthorizationContext)
);
