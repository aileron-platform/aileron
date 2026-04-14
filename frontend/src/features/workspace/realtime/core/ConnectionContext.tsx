
import { createContext, useContext } from 'react';

export interface ConnectionContextValue {
    connected: boolean;
    connecting: boolean;
    error: string | null;
    reconnect: () => void;
}

export const ConnectionContext = createContext<ConnectionContextValue | null>(null);

export const useConnectionContext = () => {
    const context = useContext(ConnectionContext);
    if (!context) {
        throw new Error('useConnectionContext must be used within a ConnectionProvider');
    }
    return context;
};
